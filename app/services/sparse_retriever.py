"""FTS5 BM25 稀疏检索：按关键词匹配返回相关切块。"""
import logging
import re

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sparse_indexer import FTS_TABLE

logger = logging.getLogger(__name__)

# FTS5 MATCH 语法中的运算符字符，需要处理
FTS5_SPECIAL_CHARS = re.compile(r'["*:^~()-]')


def build_match_query(query: str) -> str:
    """把用户查询词转成 FTS5 安全的 MATCH 表达式。

    FTS5 MATCH 有自己的语法：空格是 OR、- 是排除、括号是分组。
    用户查询词直接拼接会语法错误（如 'step-by-step'）。
    做法：按空白拆成 token，每个 token 转义后加引号，AND 连接，
    保证所有词都要出现（更精确）。
    """
    tokens = query.split()

    quoted = []
    for token in tokens:
        escaped = FTS5_SPECIAL_CHARS.sub(" ", token)
        if escaped.strip():
            quoted.append(f'"{escaped}"')

    return " AND ".join(quoted)


@dataclass(frozen=True)
class SparseResult:
    document_id: int | None
    chunk_id: int | None
    text: str
    score: float


class SparseRetriever:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
            self,
            query: str,
            knowledge_base_id: int,
            limit: int = 5,
    ) -> list[SparseResult]:
        """BM25 关键词检索。

        FTS5 的 bm25() 分数越低越相关（负数），这里取反变成越高越相关。
        """
        statement = text(
            f"""
            SELECT document_id, chunk_id, text, -bm25({FTS_TABLE}) AS score
            FROM {FTS_TABLE}
            WHERE {FTS_TABLE} MATCH :query
              AND knowledge_base_id = :knowledge_base_id
            ORDER BY score DESC
            LIMIT :limit
            """
        )

        result = await self.session.execute(
            statement,
            {
                "query": build_match_query(query),
                "knowledge_base_id": knowledge_base_id,
                "limit": limit,
            },
        )

        rows = result.all()

        return [
            SparseResult(
                document_id=row.document_id,
                chunk_id=row.chunk_id,
                text=row.text,
                score=row.score,
            )
            for row in rows
        ]
