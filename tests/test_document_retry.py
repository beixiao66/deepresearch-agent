import asyncio
from unittest.mock import AsyncMock, Mock

from app.models.document import Document, DocumentStatus
from app.services.document import DocumentService


def build_failed_document() -> Document:
    return Document(
        id=1,
        knowledge_base_id=10,
        original_filename="rag.pdf",
        storage_path="data/uploads/10/uuid.pdf",
        file_extension=".pdf",
        file_size=2048,
        mime_type="application/pdf",
        status=DocumentStatus.FAILED.value,
        error_message="qdrant down",
    )


def test_retry_document_reuses_existing_file_and_completes() -> None:
    async def run_test() -> None:
        document = build_failed_document()
        repository = Mock()
        repository.get_by_id = AsyncMock(return_value=document)

        def update_status(doc, status, error_message=None):
            doc.status = status.value
            doc.error_message = error_message

        repository.update_status = AsyncMock(side_effect=update_status)

        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        indexer = Mock()
        indexer.index_document = AsyncMock(
            return_value=(2, ["块1", "块2"])
        )

        session = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()

        service = DocumentService(
            document_repository=repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=Mock(),
            qdrant_store=Mock(),
            indexer=indexer,
            session=session,
        )
        service.file_storage.remove = AsyncMock()

        result = await service.retry_document(10, 1)

        assert result.status == DocumentStatus.COMPLETED.value
        assert result.error_message is None
        indexer.index_document.assert_awaited_once_with(
            storage_path="data/uploads/10/uuid.pdf",
            file_extension=".pdf",
            document_id=1,
            knowledge_base_id=10,
        )
        service.file_storage.remove.assert_not_awaited()

    asyncio.run(run_test())


def test_retry_document_keeps_failed_status_when_indexing_fails() -> None:
    async def run_test() -> None:
        document = build_failed_document()
        repository = Mock()
        repository.get_by_id = AsyncMock(return_value=document)

        def update_status(doc, status, error_message=None):
            doc.status = status.value
            doc.error_message = error_message

        repository.update_status = AsyncMock(side_effect=update_status)
        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        indexer = Mock()
        indexer.index_document = AsyncMock(
            side_effect=RuntimeError("qdrant down")
        )

        session = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        service = DocumentService(
            document_repository=repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=Mock(),
            qdrant_store=Mock(),
            indexer=indexer,
            session=session,
        )

        try:
            await service.retry_document(10, 1)
            assert False, "retry should raise the indexing error"
        except RuntimeError as exc:
            assert str(exc) == "qdrant down"

        assert document.status == DocumentStatus.FAILED.value
        assert document.error_message == "qdrant down"

    asyncio.run(run_test())
