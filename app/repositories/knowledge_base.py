from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
            self,
            name: str,
            description: str | None,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            name=name,
            description=description,
        )

        self.session.add(knowledge_base)
        await self.session.flush()
        await self.session.refresh(knowledge_base)

        return knowledge_base

    async def list_all(self) -> list[KnowledgeBase]:
        statement = select(KnowledgeBase).order_by(
            KnowledgeBase.id.desc()
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def get_by_id(
            self,
            knowledge_base_id: int,
    ) -> KnowledgeBase | None:
        return await self.session.get(
            KnowledgeBase,
            knowledge_base_id,
        )