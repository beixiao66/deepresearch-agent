from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.qdrant_store import (
    QdrantStore,
    get_qdrant_client,
)
from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.document import DocumentRepository
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.services.document import DocumentService
from app.services.file_storage import FileStorageService
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


def get_document_repository(
        session: DatabaseSession,
) -> DocumentRepository:
    return DocumentRepository(session)


DocumentRepositoryDependency = Annotated[
    DocumentRepository,
    Depends(get_document_repository),
]


def get_file_storage_service() -> FileStorageService:
    return FileStorageService(
        get_settings()
    )


FileStorageServiceDependency = Annotated[
    FileStorageService,
    Depends(get_file_storage_service),
]


def get_qdrant_store() -> QdrantStore:
    settings = get_settings()

    return QdrantStore(
        client=get_qdrant_client(),
        collection_name=settings.qdrant_collection,
        vector_size=1024,
    )


QdrantStoreDependency = Annotated[
    QdrantStore,
    Depends(get_qdrant_store),
]


def get_document_service(
        document_repository: DocumentRepositoryDependency,
        knowledge_base_repository: KnowledgeBaseRepositoryDependency,
        file_storage: FileStorageServiceDependency,
        qdrant_store: QdrantStoreDependency,
        session: DatabaseSession,
) -> DocumentService:
    return DocumentService(
        document_repository=document_repository,
        knowledge_base_repository=knowledge_base_repository,
        file_storage=file_storage,
        qdrant_store=qdrant_store,
        session=session,
    )


DocumentServiceDependency = Annotated[
    DocumentService,
    Depends(get_document_service),
]