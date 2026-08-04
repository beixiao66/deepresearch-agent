from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KnowledgeBaseNotFoundError, DocumentNotFoundError
from app.models.document import Document
from app.repositories.document import DocumentRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.file_storage import FileStorageService


class DocumentService:
    def __init__(
            self,
            document_repository: DocumentRepository,
            knowledge_base_repository: KnowledgeBaseRepository,
            file_storage: FileStorageService,
            session: AsyncSession,
    ) -> None:
        self.document_repository = document_repository
        self.knowledge_base_repository = (
            knowledge_base_repository
        )
        self.file_storage = file_storage
        self.session = session

    async def upload_document(
            self,
            knowledge_base_id: int,
            upload: UploadFile,
    ) -> Document:
        knowledge_base = (
            await self.knowledge_base_repository.get_by_id(
                knowledge_base_id
            )
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(
                knowledge_base_id
            )

        stored_file = await self.file_storage.save(
            knowledge_base_id=knowledge_base_id,
            upload=upload,
        )

        try:
            document = await self.document_repository.create(
                knowledge_base_id=knowledge_base_id,
                original_filename=stored_file.original_filename,
                storage_path=stored_file.storage_path,
                file_extension=stored_file.file_extension,
                file_size=stored_file.file_size,
                mime_type=stored_file.mime_type,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.file_storage.remove(
                stored_file.storage_path
            )
            raise

        return document

    async def list_by_knowledge_base(
            self,
            knowledge_base_id: int,
    ) -> list[Document]:
        knowledge_base = (
            await self.knowledge_base_repository.get_by_id(
                knowledge_base_id
            )
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(
                knowledge_base_id
            )

        return await self.document_repository.list_by_knowledge_base(
            knowledge_base_id
        )

    async def delete_document(
            self,
            knowledge_base_id: int,
            document_id: int,
    ) -> None:
        knowledge_base = (
            await self.knowledge_base_repository.get_by_id(
                knowledge_base_id
            )
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(
                knowledge_base_id
            )

        document = (
            await self.document_repository.get_by_id(
                knowledge_base_id,
                document_id,
            )
        )

        if document is None:
            raise DocumentNotFoundError(document_id)

        stored_file_path = document.storage_path

        try:
            await self.document_repository.delete(document)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.file_storage.remove(stored_file_path)