import logging
from typing import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.election_spending import MvElectionSpendingSummary
from civic_lantern.services.data.base import BaseService

logger = logging.getLogger(__name__)


class ElectionSpendingService(BaseService[MvElectionSpendingSummary]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=MvElectionSpendingSummary, db=db)

    async def get_all_spending(self) -> Sequence[MvElectionSpendingSummary]:
        """Fetch all election spending summaries ordered by cycle descending."""
        stmt = select(MvElectionSpendingSummary).order_by(
            desc(MvElectionSpendingSummary.cycle)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_spending_by_cycle(
        self, cycle: int
    ) -> MvElectionSpendingSummary | None:
        """Fetch spending summary for a specific election cycle."""
        return await self.get_by_id(cycle)
