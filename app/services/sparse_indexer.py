"""SQLite FTS5 稀疏检索：文档切块同步写入全文索引。

设计要点：
- FTS5 是 SQLite 自带虚拟表，用原生 SQL 创建（ORM 不支持）
- UNINDEXED 列只存储元数据不参与全文索引，避免误命中
- 与向量库并行：同一文档入库时同步写 FTS5，删除时同步删
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

FTS_TABLE = "document_chunks_fts"

CREATE_FTS_TABLE_SQL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
USING fts5(
    text,
    document_id UNINDEXED,
    chunk_id UNINDEXED,
    knowledge_base_id UNINDEXED
);
"""


class SparseIndexer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_table(self) -> None:
        """建表（幂等：已存在则跳过）。"""
        await self.session.execute(
            text(CREATE_FTS_TABLE_SQL)
        )

    async def index_chunks(
            self,
            document_id: int,
            knowledge_base_id: int,
            chunks: list[str],
    ) -> int:
        """写入文档所有切块到 FTS5。先删旧记录再插入（幂等重建）。"""
        await self.session.execute(
            text(
                f"DELETE FROM {FTS_TABLE} "
                "WHERE document_id = :document_id"
            ),
            {"document_id": document_id},
        )

        for chunk_index, chunk_text in enumerate(chunks):
            await self.session.execute(
                text(
                    f"INSERT INTO {FTS_TABLE} "
                    "(text, document_id, chunk_id, knowledge_base_id) "
                    "VALUES (:text, :document_id, :chunk_id, :knowledge_base_id)"
                ),
                {
                    "text": chunk_text,
                    "document_id": document_id,
                    "chunk_id": chunk_index,
                    "knowledge_base_id": knowledge_base_id,
                },
            )

        await self.session.commit()

        return len(chunks)

    async def delete_document(
            self,
            document_id: int,
    ) -> None:
        """删除文档在 FTS5 中的全部记录。"""
        await self.session.execute(
            text(
                f"DELETE FROM {FTS_TABLE} "
                "WHERE document_id = :document_id"
            ),
            {"document_id": document_id},
        )
        await self.session.commit()
