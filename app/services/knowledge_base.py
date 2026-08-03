from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.schemas.knowledge_base import KnowledgeBaseCreate

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    KnowledgeBaseNameConflictError,
    KnowledgeBaseNotFoundError,
)


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
        except IntegrityError as exc:
            await self.session.rollback()
            raise KnowledgeBaseNameConflictError(
                data.name
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        return knowledge_base

    async def list_all(self) -> list[KnowledgeBase]:
        return await self.repository.list_all()

    async def get_by_id(
            self,
            knowledge_base_id: int,
    ) -> KnowledgeBase:
        knowledge_base = await self.repository.get_by_id(
            knowledge_base_id
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(
                knowledge_base_id
            )

        return knowledge_base