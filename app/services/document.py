import logging

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentNotFoundError,
    KnowledgeBaseNotFoundError,
)
from app.models.document import Document, DocumentStatus
from app.repositories.document import DocumentRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.services.document_indexer import DocumentIndexer
from app.services.file_storage import FileStorageService
from app.services.qdrant_store import QdrantStore
from app.services.sparse_indexer import SparseIndexer

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
            self,
            document_repository: DocumentRepository,
            knowledge_base_repository: KnowledgeBaseRepository,
            file_storage: FileStorageService,
            qdrant_store: QdrantStore,
            indexer: DocumentIndexer,
            session: AsyncSession,
    ) -> None:
        self.document_repository = document_repository
        self.knowledge_base_repository = (
            knowledge_base_repository
        )
        self.file_storage = file_storage
        self.qdrant_store = qdrant_store
        self.indexer = indexer
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

        await self._index_after_upload(
            knowledge_base_id,
            document,
        )

        await self.session.refresh(document)

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
        document_id = document.id

        try:
            await self.document_repository.delete(document)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.file_storage.remove(stored_file_path)
        await self.qdrant_store.delete_document_points(
            document_id
        )

        sparse_indexer = SparseIndexer(self.session)
        await sparse_indexer.delete_document(document_id)

    async def retry_document(
            self,
            knowledge_base_id: int,
            document_id: int,
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

        document = (
            await self.document_repository.get_by_id(
                knowledge_base_id,
                document_id,
            )
        )

        if document is None:
            raise DocumentNotFoundError(document_id)

        if document.status != DocumentStatus.FAILED.value:
            return document

        await self._index_document_content(
            knowledge_base_id=knowledge_base_id,
            document=document,
            raise_on_error=True,
        )
        await self.session.refresh(document)
        return document

    async def index_document(
            self,
            knowledge_base_id: int,
            document_id: int,
            indexer: DocumentIndexer,
    ) -> int:
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

        await self.document_repository.update_status(
            document,
            DocumentStatus.PROCESSING,
        )
        await self.session.commit()

        try:
            point_count, chunk_texts = await indexer.index_document(
                storage_path=document.storage_path,
                file_extension=document.file_extension,
                document_id=document.id,
                knowledge_base_id=knowledge_base_id,
            )

            sparse_indexer = SparseIndexer(self.session)
            await sparse_indexer.ensure_table()
            await sparse_indexer.index_chunks(
                document_id=document.id,
                knowledge_base_id=knowledge_base_id,
                chunks=chunk_texts,
            )

            await self.document_repository.update_status(
                document,
                DocumentStatus.COMPLETED,
            )
            await self.session.commit()
        except Exception as exc:
            await self.document_repository.update_status(
                document,
                DocumentStatus.FAILED,
                error_message="文档处理失败，请重试或重新上传",
            )
            await self.session.commit()
            raise

        return point_count

    async def _index_document_content(
            self,
            knowledge_base_id: int,
            document: Document,
            raise_on_error: bool,
    ) -> None:
        try:
            await self.document_repository.update_status(
                document,
                DocumentStatus.PROCESSING,
            )
            await self.session.commit()

            _, chunk_texts = await self.indexer.index_document(
                storage_path=document.storage_path,
                file_extension=document.file_extension,
                document_id=document.id,
                knowledge_base_id=knowledge_base_id,
            )

            sparse_indexer = SparseIndexer(self.session)
            await sparse_indexer.ensure_table()
            await sparse_indexer.index_chunks(
                document_id=document.id,
                knowledge_base_id=knowledge_base_id,
                chunks=chunk_texts,
            )

            await self.document_repository.update_status(
                document,
                DocumentStatus.COMPLETED,
            )
            await self.session.commit()
        except Exception as exc:
            await self.document_repository.update_status(
                document,
                DocumentStatus.FAILED,
                error_message="文档处理失败，请重试或重新上传",
            )
            await self.session.commit()
            logger.error(
                "Document indexing failed: document_id=%d, error=%s",
                document.id,
                exc,
                exc_info=True,
            )
            if raise_on_error:
                raise

    async def _index_after_upload(
            self,
            knowledge_base_id: int,
            document: Document,
    ) -> None:
        await self._index_document_content(
            knowledge_base_id=knowledge_base_id,
            document=document,
            raise_on_error=False,
        )
