import logging
from typing import Any, Dict, Generic, List, Type, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy import exc, inspect, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseService(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db
        self.pk_name = inspect(self.model).primary_key[0].name

        if not hasattr(self, "index_elements"):
            self.index_elements = [self.pk_name]

    async def get_by_id(self, id: str):
        """Fetch a single record by its primary key."""
        pk_column = getattr(self.model, self.pk_name)
        result = await self.db.execute(select(self.model).filter(pk_column == id))
        return result.scalars().first()

    async def upsert_batch(
        self, data: Union[List[dict], List[BaseModel]], batch_size: int = 500
    ) -> Dict[str, Any]:
        """
        Generic upsert. Tries to insert in batches.
        If a batch fails, falls back to row-by-row processing.
        """
        if not data:
            return {"inserted": 0, "updated": 0, "errors": 0, "failed_ids": []}

        if data and isinstance(data[0], BaseModel):
            data = [item.model_dump() for item in data]

        stats = {"inserted": 0, "updated": 0, "errors": 0, "failed_ids": []}

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]

            try:
                inserted, updated = await self._execute_upsert(batch)
                await self.db.commit()

                stats["inserted"] += inserted
                stats["updated"] += updated
                logger.debug(
                    f"Batch {self.model.__name__}: "
                    f"{inserted} inserted, {updated} updated"
                )

            except exc.SQLAlchemyError as e:
                await self.db.rollback()
                logger.warning(
                    f"Batch failed for {self.model.__name__} (idx {i}). "
                    f"Switching to row-by-row. Error: {e}"
                )

                batch_stats = await self._process_batch_individually(batch)

                stats["inserted"] += batch_stats["inserted"]
                stats["updated"] += batch_stats["updated"]
                stats["errors"] += batch_stats["error_count"]
                stats["failed_ids"].extend(batch_stats["failed_ids"])

        logger.info(
            f"Upsert complete. "
            f"Inserted: {stats['inserted']}, "
            f"Updated: {stats['updated']}, "
            f"Errors: {stats['errors']}"
        )

        return stats

    async def _process_batch_individually(self, batch: List[dict]) -> Dict[str, Any]:
        """Helper to process a failed batch one row at a time."""
        stats = {"inserted": 0, "updated": 0, "error_count": 0, "failed_ids": []}

        for row in batch:
            row_id = row.get(self.pk_name, "UNKNOWN")

            try:
                async with self.db.begin_nested():
                    inserted, updated = await self._execute_upsert([row])

                stats["inserted"] += inserted
                stats["updated"] += updated

            except Exception as e:
                stats["error_count"] += 1
                stats["failed_ids"].append(row_id)
                logger.error(
                    f"Failed {self.model.__name__} [{row_id}]: {type(e).__name__} - {e}"
                )

        await self.db.commit()
        return stats

    async def _execute_upsert(self, values: List[dict]) -> tuple[int, int]:
        """Constructs and executes the PostgreSQL upsert statement.

        Returns (inserted_count, updated_count) using the xmax system column:
        xmax = 0 means the row was inserted; xmax != 0 means it was updated.
        """
        stmt = insert(self.model).values(values)

        update_cols = {
            col.name: col
            for col in stmt.excluded
            if col.name not in self.index_elements and col.name != "created_at"
        }

        # Only update when at least one meaningful column actually changed.
        # Excludes updated_at (trigger-managed) to avoid counting timestamp-only diffs.
        table = self.model.__table__
        changed_conditions = [
            table.c[name].is_distinct_from(excl_col)
            for name, excl_col in update_cols.items()
            if name != "updated_at"
        ]

        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=self.index_elements,
            set_=update_cols,
            where=or_(*changed_conditions) if changed_conditions else None,
        ).returning(literal_column("xmax::text::bigint"))

        result = await self.db.execute(upsert_stmt)
        rows = result.fetchall()
        inserted = sum(1 for row in rows if row[0] == 0)
        updated = len(rows) - inserted
        return inserted, updated
