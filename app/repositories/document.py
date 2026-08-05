from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
            self,
            knowledge_base_id: int,
            original_filename: str,
            storage_path: str,
            file_extension: str,
            file_size: int,
            mime_type: str | None,
    ) -> Document:
        document = Document(
            knowledge_base_id=knowledge_base_id,
            original_filename=original_filename,
            storage_path=storage_path,
            file_extension=file_extension,
            file_size=file_size,
            mime_type=mime_type,
            status=DocumentStatus.PENDING.value,
        )

        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)

        return document

    async def list_by_knowledge_base(
            self,
            knowledge_base_id: int,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(
                Document.knowledge_base_id
                == knowledge_base_id
            )
            .order_by(Document.id.desc())
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def get_by_id(
            self,
            knowledge_base_id: int,
            document_id: int,
    ) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.knowledge_base_id
            == knowledge_base_id,
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def delete(
            self,
            document: Document,
    ) -> None:
        await self.session.delete(document)

    async def update_status(
            self,
            document: Document,
            status: DocumentStatus,
            error_message: str | None = None,
    ) -> None:
        document.status = status.value
        document.error_message = error_message

