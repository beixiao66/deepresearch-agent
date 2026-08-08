"""交叉编码器重排序：对召回候选重新打分，精排 top N。

调用百炼 qwen3-rerank 模型（compatible-api /reranks 端点）。

注意：rerank 端点与 embedding/chat 的 compatible-mode/v1 不同，
需要独立的 base_url（https://dashscope.aliyuncs.com/compatible-api/v1）。
"""
import logging

from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RERANK_MODEL = "qwen3-rerank"
RERANK_BASE_URL = (
    "https://dashscope.aliyuncs.com/compatible-api/v1"
)


@dataclass(frozen=True)
class RerankedItem:
    index: int
    relevance_score: float
    text: str


class Reranker:
    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def rerank(
            self,
            query: str,
            documents: list[str],
            top_n: int = 5,
    ) -> list[RerankedItem]:
        """对候选文档重新打分，返回排序后的结果。

        documents 需要保留原始顺序（结果中的 index 对应输入位置）。
        """
        if not documents:
            return []

        response = self.client.post(
            "/reranks",
            body={
                "model": RERANK_MODEL,
                "query": query,
                "documents": documents,
            },
            cast_to=object,
        )

        results = response["results"]

        logger.info(
            "rerank: input=%d, returned=%d",
            len(documents),
            len(results),
        )

        return [
            RerankedItem(
                index=item["index"],
                relevance_score=item["relevance_score"],
                text=documents[item["index"]],
            )
            for item in results[:top_n]
        ]


@lru_cache
def get_reranker() -> Reranker:
    """构建全局复用的重排器（独立 base_url 的 OpenAI 兼容客户端）。"""
    settings = get_settings()

    return Reranker(
        client=OpenAI(
            api_key=settings.dashscope_api_key.get_secret_value(),
            base_url=RERANK_BASE_URL,
        )
    )
