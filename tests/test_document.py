from datetime import datetime, timezone

from app.models.document import Document, DocumentStatus


def test_document_model_contains_upload_metadata() -> None:
    timestamp = datetime.now(timezone.utc)

    document = Document(
        id=1,
        knowledge_base_id=10,
        original_filename="RAG手册.pdf",
        storage_path="data/uploads/abc123.pdf",
        file_extension=".pdf",
        file_size=2048,
        mime_type="application/pdf",
        status=DocumentStatus.PENDING.value,
        created_at=timestamp,
        updated_at=timestamp,
    )

    assert document.knowledge_base_id == 10
    assert document.original_filename == "RAG手册.pdf"
    assert document.storage_path == "data/uploads/abc123.pdf"
    assert document.file_extension == ".pdf"
    assert document.file_size == 2048
    assert document.mime_type == "application/pdf"
    assert document.status == "pending"
    assert document.error_message is None


def test_document_status_contains_supported_states() -> None:
    assert DocumentStatus.PENDING.value == "pending"
    assert DocumentStatus.PROCESSING.value == "processing"
    assert DocumentStatus.COMPLETED.value == "completed"
    assert DocumentStatus.FAILED.value == "failed"