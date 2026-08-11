import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.document import Document, DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.knowledge_base import KnowledgeBaseService
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    KnowledgeBaseNameConflictError,
    KnowledgeBaseNotFoundError,
)

def test_knowledge_base_service_commits_create() -> None:
    async def run_test() -> None:
        knowledge_base = KnowledgeBase(
            id=1,
            name="AI 技术资料库",
            description=None,
        )

        repository = Mock()
        repository.create = AsyncMock(
            return_value=knowledge_base
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = KnowledgeBaseService(
            repository=repository,
            session=session,
        )

        result = await service.create(
            KnowledgeBaseCreate(
                name="AI 技术资料库",
            )
        )

        assert result is knowledge_base
        repository.create.assert_awaited_once_with(
            name="AI 技术资料库",
            description=None,
        )
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    asyncio.run(run_test())


def test_knowledge_base_service_rolls_back_on_error() -> None:
    async def run_test() -> None:
        repository = Mock()
        repository.create = AsyncMock(
            side_effect=RuntimeError("database failed")
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = KnowledgeBaseService(
            repository=repository,
            session=session,
        )

        with pytest.raises(
                RuntimeError,
                match="database failed",
        ):
            await service.create(
                KnowledgeBaseCreate(
                    name="AI 技术资料库",
                )
            )

        session.commit.assert_not_awaited()
        session.rollback.assert_awaited_once()

    asyncio.run(run_test())


def test_knowledge_base_service_raises_not_found() -> None:
    async def run_test() -> None:
        repository = Mock()
        repository.get_by_id = AsyncMock(
            return_value=None
        )

        session = Mock()
        service = KnowledgeBaseService(
            repository=repository,
            session=session,
        )

        with pytest.raises(
                KnowledgeBaseNotFoundError,
        ) as exc_info:
            await service.get_by_id(999)

        assert exc_info.value.knowledge_base_id == 999
        repository.get_by_id.assert_awaited_once_with(999)

    asyncio.run(run_test())


def test_knowledge_base_service_maps_name_conflict() -> None:
    async def run_test() -> None:
        repository = Mock()
        repository.create = AsyncMock(
            side_effect=IntegrityError(
                statement="INSERT INTO knowledge_base",
                params={},
                orig=Exception("unique constraint failed"),
            )
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = KnowledgeBaseService(
            repository=repository,
            session=session,
        )

        with pytest.raises(
                KnowledgeBaseNameConflictError,
        ) as exc_info:
            await service.create(
                KnowledgeBaseCreate(
                    name="AI 技术资料库",
                )
            )

        assert exc_info.value.name == "AI 技术资料库"
        session.commit.assert_not_awaited()
        session.rollback.assert_awaited_once()

    asyncio.run(run_test())


def build_document(knowledge_base_id: int, document_id: int) -> Document:
    return Document(
        id=document_id,
        knowledge_base_id=knowledge_base_id,
        original_filename="test.md",
        storage_path=f"data/uploads/{knowledge_base_id}/uuid.md",
        file_extension=".md",
        file_size=1024,
        mime_type="text/markdown",
        status=DocumentStatus.COMPLETED.value,
    )


def test_delete_knowledge_base_cleans_all_storage() -> None:
    async def run_test() -> None:
        knowledge_base = KnowledgeBase(
            id=1,
            name="AI 技术资料库",
            description=None,
        )
        document = build_document(1, 10)

        repository = Mock()
        repository.get_by_id = AsyncMock(
            return_value=knowledge_base
        )
        repository.list_documents = AsyncMock(
            return_value=[document]
        )
        repository.delete = AsyncMock()

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        file_storage = Mock()
        file_storage.upload_root = Path("data/uploads")
        file_storage.remove = AsyncMock()

        qdrant_store = Mock()
        qdrant_store.delete_knowledge_base_points = AsyncMock()

        service = KnowledgeBaseService(
            repository=repository,
            session=session,
            file_storage=file_storage,
            qdrant_store=qdrant_store,
        )

        await service.delete(1)

        repository.delete.assert_awaited_once_with(
            knowledge_base
        )
        session.commit.assert_awaited()
        file_storage.remove.assert_awaited_once_with(
            document.storage_path
        )
        qdrant_store.delete_knowledge_base_points.assert_awaited_once_with(
            1
        )

    asyncio.run(run_test())


def test_delete_knowledge_base_missing_raises_not_found() -> None:
    async def run_test() -> None:
        repository = Mock()
        repository.get_by_id = AsyncMock(return_value=None)

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = KnowledgeBaseService(
            repository=repository,
            session=session,
        )

        with pytest.raises(
                KnowledgeBaseNotFoundError,
        ) as exc_info:
            await service.delete(999)

        assert exc_info.value.knowledge_base_id == 999
        repository.delete.assert_not_called()
        session.commit.assert_not_awaited()

    asyncio.run(run_test())