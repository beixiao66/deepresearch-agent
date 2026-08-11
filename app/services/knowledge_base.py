from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import (
    KnowledgeBaseRepository,
)
from app.schemas.knowledge_base import KnowledgeBaseCreate

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    KnowledgeBaseNameConflictError,
    KnowledgeBaseNotFoundError,
)
from app.services.file_storage import FileStorageService
from app.services.qdrant_store import QdrantStore
from app.services.sparse_indexer import SparseIndexer


class KnowledgeBaseService:
    def __init__(
            self,
            repository: KnowledgeBaseRepository,
            session: AsyncSession,
            file_storage: FileStorageService | None = None,
            qdrant_store: QdrantStore | None = None,
    ) -> None:
        self.repository = repository
        self.session = session
        self.file_storage = file_storage
        self.qdrant_store = qdrant_store

    async def create(
            self,
            data: KnowledgeBaseCreate,
    ) -> KnowledgeBase:
        try:
            knowledge_base = await self.repository.create(
                name=data.name,
                description=data.description,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise KnowledgeBaseNameConflictError(
                data.name
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        return knowledge_base

    async def list_all(self) -> list[KnowledgeBase]:
        return await self.repository.list_all()

    async def get_by_id(
            self,
            knowledge_base_id: int,
    ) -> KnowledgeBase:
        knowledge_base = await self.repository.get_by_id(
            knowledge_base_id
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(
                knowledge_base_id
            )

        return knowledge_base

    async def delete(
            self,
            knowledge_base_id: int,
    ) -> None:
        """删除知识库，级联清理数据库记录、磁盘文件、Qdrant 向量与 FTS5 索引。"""
        knowledge_base = await self.repository.get_by_id(
            knowledge_base_id
        )

        if knowledge_base is None:
            raise KnowledgeBaseNotFoundError(
                knowledge_base_id
            )

        # 先收集该知识库下的文档 ID 与存储路径（删除记录后无法再查）
        documents = await self.repository.list_documents(
            knowledge_base_id
        )
        document_ids = [document.id for document in documents]
        storage_paths = [
            document.storage_path
            for document in documents
        ]
        upload_directory = (
            self.file_storage.upload_root
            / str(knowledge_base_id)
            if self.file_storage is not None
            else None
        )

        try:
            await self.repository.delete(knowledge_base)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        # 磁盘文件清理
        if self.file_storage is not None:
            for storage_path in storage_paths:
                try:
                    await self.file_storage.remove(storage_path)
                except Exception:
                    # 文件清理失败不阻塞整体删除，只记录
                    pass

            if upload_directory is not None:
                import anyio
                try:
                    if upload_directory.exists():
                        await anyio.to_thread.run_sync(
                            _remove_dir,
                            upload_directory,
                        )
                except Exception:
                    pass

        # Qdrant 向量清理（按 knowledge_base_id 一次删除全部点）
        if self.qdrant_store is not None:
            try:
                await self.qdrant_store.delete_knowledge_base_points(
                    knowledge_base_id
                )
            except Exception:
                pass

        # FTS5 索引清理（按 knowledge_base_id 删除）
        try:
            sparse_indexer = SparseIndexer(self.session)
            await sparse_indexer.delete_knowledge_base(
                knowledge_base_id
            )
        except Exception:
            pass


def _remove_dir(directory) -> None:
    import shutil
    shutil.rmtree(directory, ignore_errors=True)
