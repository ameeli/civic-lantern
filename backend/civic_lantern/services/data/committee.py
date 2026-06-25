from sqlalchemy.ext.asyncio import AsyncSession

from civic_lantern.db.models.committee import Committee
from civic_lantern.services.data.base import BaseService


class CommitteeService(BaseService[Committee]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(model=Committee, db=db)
