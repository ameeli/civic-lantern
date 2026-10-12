import logging
from typing import Any, Dict, Generic, List, Sequence, Type, TypedDict, TypeVar

from pydantic import BaseModel
from sqlalchemy import exc, func, inspect, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=DeclarativeBase)


class UpsertStats(TypedDict):
    inserted: int
    updated: int
    errors: int
    failed_ids: List[Any]


class BaseService(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db
        mapper = inspect(self.model)
        assert mapper is not None
        self.pk_name = mapper.primary_key[0].name
        self.pk_names = [col.name for col in mapper.primary_key]

        if not hasattr(self, "index_elements"):
            self.index_elements = list(self.pk_names)

    def _apply_filters(self, stmt: Any, **filters: Any) -> Any:
        """Apply equality filters to a select statement, skipping None values."""
        for field, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, field) == value)
        return stmt

    async def get_by_id(self, id: Any):
        """Fetch a single record by its primary key."""
        pk_column = getattr(self.model, self.pk_name)
        result = await self.db.execute(select(self.model).filter(pk_column == id))
        return result.scalars().first()

    async def _paginate(
        self, base_stmt: Any, sorted_stmt: Any, limit: int, offset: int
    ) -> Dict[str, Any]:
        """Count `base_stmt` and fetch one page from `sorted_stmt`.

        `sorted_stmt` must already carry the same filters as `base_stmt` plus
        an ORDER BY, since it's what gets limit/offset applied for the page.
        """
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = (await self.db.execute(count_stmt)).scalar() or 0

        page_stmt = sorted_stmt.limit(limit).offset(offset)
        result = await self.db.execute(page_stmt)

        return {
            "items": list(result.scalars().all()),
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    async def upsert_batch(
        self, items: Sequence[BaseModel], batch_size: int = 500
    ) -> UpsertStats:
        """Upsert `items` on the full primary key, in batches, keeping only the
        fields that are table columns.

        Each batch runs in a savepoint; a batch that fails is rolled back and
        retried row by row, so only its bad rows are skipped (and reported in
        `failed_ids`). Doesn't commit: the caller owns the transaction, so a
        later failure can roll back every batch. An error that dropped the
        connection is re-raised rather than retried.
        """
        stats: UpsertStats = {
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "failed_ids": [],
        }
        table_columns = {col.name for col in self.model.__table__.columns}
        rows = [
            {k: v for k, v in item.model_dump().items() if k in table_columns}
            for item in items
        ]

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]

            try:
                async with self.db.begin_nested():
                    inserted, updated = await self._execute_upsert(batch)
                stats["inserted"] += inserted
                stats["updated"] += updated
                logger.debug(
                    f"Batch {self.model.__name__}: "
                    f"{inserted} inserted, {updated} updated"
                )

            except exc.SQLAlchemyError as e:
                if self._connection_invalidated(e):
                    raise
                logger.warning(
                    f"Batch failed for {self.model.__name__} (idx {i}). "
                    f"Switching to row-by-row. Error: {e}"
                )
                batch_stats = await self._process_batch_individually(batch)
                stats["inserted"] += batch_stats["inserted"]
                stats["updated"] += batch_stats["updated"]
                stats["errors"] += batch_stats["errors"]
                stats["failed_ids"].extend(batch_stats["failed_ids"])

        logger.info(
            f"Upsert complete. "
            f"Inserted: {stats['inserted']}, "
            f"Updated: {stats['updated']}, "
            f"Errors: {stats['errors']}"
        )

        return stats

    async def _process_batch_individually(self, batch: List[dict]) -> UpsertStats:
        """Upsert a failed batch one row at a time, each in its own savepoint."""
        stats: UpsertStats = {
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "failed_ids": [],
        }

        for row in batch:
            row_id = self._row_key(row)

            try:
                async with self.db.begin_nested():
                    inserted, updated = await self._execute_upsert([row])

                stats["inserted"] += inserted
                stats["updated"] += updated

            except Exception as e:
                if self._connection_invalidated(e):
                    raise
                stats["errors"] += 1
                stats["failed_ids"].append(row_id)
                logger.error(
                    f"Failed {self.model.__name__} [{row_id}]: {type(e).__name__} - {e}"
                )

        return stats

    @staticmethod
    def _connection_invalidated(e: Exception) -> bool:
        """Whether `e` dropped the connection, aborting the caller's transaction."""
        return isinstance(e, exc.DBAPIError) and e.connection_invalidated

    def _row_key(self, row: dict) -> Any:
        """The row's primary key for error reports: a scalar for a single-column
        key, a tuple of plain values (enums as .value) for a composite one."""
        values = [row.get(name, "UNKNOWN") for name in self.pk_names]
        values = [getattr(v, "value", v) for v in values]
        return values[0] if len(values) == 1 else tuple(values)

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

        upsert_stmt: Any = stmt.on_conflict_do_update(
            index_elements=self.index_elements,
            set_=update_cols,
            where=or_(*changed_conditions) if changed_conditions else None,
        ).returning(literal_column("xmax::text::bigint"))

        result = await self.db.execute(upsert_stmt)
        rows = result.fetchall()
        inserted = sum(1 for row in rows if row[0] == 0)
        updated = len(rows) - inserted
        return inserted, updated
