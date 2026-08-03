from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.schemas.knowledge_base import KnowledgeBaseCreate


class KnowledgeBaseService:
    def __init__(
            self,
            repository: KnowledgeBaseRepository,
            session: AsyncSession,
    ) -> None:
        self.repository = repository
        self.session = session

    async def create(
            self,
            data: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        try:
            knowledge_base = await self.repository.create(
                name=data.name,
                description=data.description,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return knowledge_base

    async def list_all(self) -> list[KnowledgeBase]:
        return await self.repository.list_all()

    async def get_by_id(
            self,
            knowledge_base_id: int,
    ) -> KnowledgeBase | None:
        return await self.repository.get_by_id(
            knowledge_base_id
        )