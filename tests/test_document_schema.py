from datetime import datetime, timezone

from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentResponse


def test_document_response_reads_orm_attributes() -> None:
    timestamp = datetime.now(timezone.utc)
    document = Document(
        id=1,
        knowledge_base_id=10,
        original_filename="RAG手册.pdf",
        storage_path="data/uploads/internal-file.pdf",
        file_extension=".pdf",
        file_size=2048,
        mime_type="application/pdf",
        status=DocumentStatus.PENDING.value,
        error_message=None,
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = DocumentResponse.model_validate(document)

    assert response.id == 1
    assert response.original_filename == "RAG手册.pdf"
    assert response.status is DocumentStatus.PENDING

    response_data = response.model_dump()

    assert "storage_path" not in response_data