from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    original_filename: str
    file_extension: str
    file_size: int
    mime_type: str | None
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime