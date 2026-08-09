"""文档状态流转测试：pending -> processing -> completed / failed。"""
import asyncio
from unittest.mock import AsyncMock, Mock

from app.models.document import Document, DocumentStatus
from app.services.document import DocumentService


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


def build_service(
        document_repository: Mock,
        session: Mock,
        indexer: Mock = None,
) -> DocumentService:
    knowledge_base_repository = Mock()
    knowledge_base_repository.get_by_id = AsyncMock(
        return_value=object()
    )

    return DocumentService(
        document_repository=document_repository,
        knowledge_base_repository=knowledge_base_repository,
        file_storage=Mock(),
        qdrant_store=Mock(),
        indexer=indexer or Mock(),
        session=session,
    )


def test_upload_transitions_pending_processing_completed() -> None:
    async def run_test() -> None:
        document = build_document()
        status_history: list[str] = []

        def record_status(doc, status, error_message=None):
            status_history.append(status.value)
            doc.status = status.value

        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        document_repository = Mock()
        document_repository.create = AsyncMock(
            return_value=document
        )
        document_repository.update_status = AsyncMock(
            side_effect=record_status
        )

        indexer = Mock()
        indexer.index_document = AsyncMock(
            return_value=(5, ["块1", "块2", "块3"])
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()

        service = DocumentService(
            document_repository=document_repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=Mock(),
            qdrant_store=Mock(),
            indexer=indexer,
            session=session,
        )
        file_storage = service.file_storage
        file_storage.save = AsyncMock()
        file_storage.remove = AsyncMock()

        result = await service.upload_document(
            knowledge_base_id=10,
            upload=Mock(),
        )

        # 状态流转：pending(初始) -> processing -> completed
        assert status_history == [
            DocumentStatus.PROCESSING.value,
            DocumentStatus.COMPLETED.value,
        ]
        assert result.status == DocumentStatus.COMPLETED.value

    asyncio.run(run_test())


def test_upload_index_failure_marks_failed() -> None:
    async def run_test() -> None:
        document = build_document()
        status_history: list[str] = []

        def record_status(doc, status, error_message=None):
            status_history.append(status.value)
            doc.status = status.value
            doc.error_message = error_message

        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        document_repository = Mock()
        document_repository.create = AsyncMock(
            return_value=document
        )
        document_repository.update_status = AsyncMock(
            side_effect=record_status
        )

        indexer = Mock()
        indexer.index_document = AsyncMock(
            side_effect=RuntimeError("embedding failed")
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()

        service = DocumentService(
            document_repository=document_repository,
            knowledge_base_repository=knowledge_base_repository,
            file_storage=Mock(),
            qdrant_store=Mock(),
            indexer=indexer,
            session=session,
        )
        file_storage = service.file_storage
        file_storage.save = AsyncMock()
        file_storage.remove = AsyncMock()

        await service.upload_document(
            knowledge_base_id=10,
            upload=Mock(),
        )

        # 索引失败：processing -> failed，且记录错误信息
        assert status_history[-1] == DocumentStatus.FAILED.value
        assert document.error_message == "embedding failed"
        # 上传本身不抛错（索引失败已吞掉，文档保留为 failed）
        assert document.status == DocumentStatus.FAILED.value

    asyncio.run(run_test())


def test_index_document_success_transitions() -> None:
    async def run_test() -> None:
        document = build_document()
        status_history: list[str] = []

        def record_status(doc, status, error_message=None):
            status_history.append(status.value)
            doc.status = status.value

        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        document_repository = Mock()
        document_repository.get_by_id = AsyncMock(
            return_value=document
        )
        document_repository.update_status = AsyncMock(
            side_effect=record_status
        )

        indexer = Mock()
        indexer.index_document = AsyncMock(
            return_value=(3, ["块1", "块2", "块3"])
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()

        service = build_service(
            document_repository,
            session,
            indexer,
        )

        point_count = await service.index_document(
            knowledge_base_id=10,
            document_id=1,
            indexer=indexer,
        )

        assert point_count == 3
        assert status_history == [
            DocumentStatus.PROCESSING.value,
            DocumentStatus.COMPLETED.value,
        ]

    asyncio.run(run_test())


def test_index_document_failure_marks_failed_and_raises() -> None:
    async def run_test() -> None:
        document = build_document()
        status_history: list[str] = []

        def record_status(doc, status, error_message=None):
            status_history.append(status.value)
            doc.status = status.value
            doc.error_message = error_message

        knowledge_base_repository = Mock()
        knowledge_base_repository.get_by_id = AsyncMock(
            return_value=object()
        )

        document_repository = Mock()
        document_repository.get_by_id = AsyncMock(
            return_value=document
        )
        document_repository.update_status = AsyncMock(
            side_effect=record_status
        )

        indexer = Mock()
        indexer.index_document = AsyncMock(
            side_effect=RuntimeError("qdrant down")
        )

        session = Mock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()

        service = build_service(
            document_repository,
            session,
            indexer,
        )

        try:
            await service.index_document(
                knowledge_base_id=10,
                document_id=1,
                indexer=indexer,
            )
            assert False, "should have raised"
        except RuntimeError:
            pass

        # processing -> failed，且异常继续上抛
        assert status_history[-1] == DocumentStatus.FAILED.value
        assert document.error_message == "qdrant down"

    asyncio.run(run_test())
