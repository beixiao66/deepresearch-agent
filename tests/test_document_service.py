import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import KnowledgeBaseNotFoundError
from app.models.document import Document, DocumentStatus
from app.services.document import DocumentService
from app.services.file_storage import StoredFile


def build_stored_file() -> StoredFile:
    return StoredFile(
        original_filename="rag.pdf",
        storage_path="data/uploads/10/uuid.pdf",
        file_extension=".pdf",
        file_size=2048,
        mime_type="application/pdf",
    )


def build_document() -> Document:
    return Document(
        id=1,
        knowledge_base_id=10,
        original_filename="rag.pdf",
        storage_path="data/uploads/10/uuid.pdf",
        file_extension=".pdf",
        file_size=2048,
        mime_type="application/pdf",
        status=DocumentStatus.PENDING.value,
    )


def test_upload_document_success_commits() -> None:
    async def run_test() -> None:
        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        file_storage = Mock()
        file_storage.save = AsyncMock(
            return_value=build_stored_file()
        )
        file_storage.remove = AsyncMock()

        document_repository = Mock()
        document_repository.create = AsyncMock(
            return_value=build_document()
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = DocumentService(
            document_repository=document_repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=file_storage,
            session=session,
        )

        result = await service.upload_document(
            knowledge_base_id=10,
            upload=Mock(),
        )

        assert result.id == 1
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        file_storage.remove.assert_not_awaited()

    asyncio.run(run_test())


def test_upload_document_missing_knowledge_base() -> None:
    async def run_test() -> None:
        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=None
        )

        file_storage = Mock()
        file_storage.save = AsyncMock()
        file_storage.remove = AsyncMock()

        document_repository = Mock()
        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = DocumentService(
            document_repository=document_repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=file_storage,
            session=session,
        )

        with pytest.raises(
                KnowledgeBaseNotFoundError,
        ) as exc_info:
            await service.upload_document(
                knowledge_base_id=999,
                upload=Mock(),
            )

        assert exc_info.value.knowledge_base_id == 999
        file_storage.save.assert_not_awaited()
        file_storage.remove.assert_not_awaited()
        session.rollback.assert_not_awaited()

    asyncio.run(run_test())


def test_upload_document_rolls_back_and_removes_file() -> None:
    async def run_test() -> None:
        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        file_storage = Mock()
        file_storage.save = AsyncMock(
            return_value=build_stored_file()
        )
        file_storage.remove = AsyncMock()

        document_repository = Mock()
        document_repository.create = AsyncMock(
            side_effect=RuntimeError("database failed")
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        service = DocumentService(
            document_repository=document_repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=file_storage,
            session=session,
        )

        with pytest.raises(
                RuntimeError,
                match="database failed",
        ):
            await service.upload_document(
                knowledge_base_id=10,
                upload=Mock(),
            )

        session.commit.assert_not_awaited()
        session.rollback.assert_awaited_once()
        file_storage.remove.assert_awaited_once_with(
            "data/uploads/10/uuid.pdf"
        )

    asyncio.run(run_test())