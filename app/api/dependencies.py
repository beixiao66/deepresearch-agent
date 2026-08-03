from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.services.knowledge_base import KnowledgeBaseService

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


def get_knowledge_base_repository(
        session: DatabaseSession,
) -> KnowledgeBaseRepository:
    return KnowledgeBaseRepository(session)


KnowledgeBaseRepositoryDependency = Annotated[
    KnowledgeBaseRepository,
    Depends(get_knowledge_base_repository),
]


def get_knowledge_base_service(
        repository: KnowledgeBaseRepositoryDependency,
        session: DatabaseSession,
) -> KnowledgeBaseService:
    return KnowledgeBaseService(
        repository=repository,
        session=session,
    )


KnowledgeBaseServiceDependency = Annotated[
    KnowledgeBaseService,
    Depends(get_knowledge_base_service),
]