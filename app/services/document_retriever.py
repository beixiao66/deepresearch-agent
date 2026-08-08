import logging

from app.services.document_embedder import DocumentEmbedder
from app.services.qdrant_store import QdrantStore, SearchResult
from app.services.reranker import Reranker
from app.services.rrf import FusionItem, rrf_fuse
from app.services.sparse_retriever import SparseRetriever

logger = logging.getLogger(__name__)


class DocumentRetriever:
    def __init__(
            self,
            embedder: DocumentEmbedder,
            qdrant_store: QdrantStore,
            sparse_retriever: SparseRetriever | None = None,
            reranker: Reranker | None = None,
    ) -> None:
        self.embedder = embedder
        self.qdrant_store = qdrant_store
        self.sparse_retriever = sparse_retriever
        self.reranker = reranker

    async def retrieve(
            self,
            question: str,
            knowledge_base_id: int,
            limit: int = 5,
    ) -> list[SearchResult]:
        """纯向量检索（原行为）。"""
        query_vector = await self.embedder.embed_texts(
            [question]
        )

        return await self.qdrant_store.search(
            query_vector=query_vector[0],
            knowledge_base_id=knowledge_base_id,
            limit=limit,
        )

    async def retrieve_hybrid(
            self,
            question: str,
            knowledge_base_id: int,
            limit: int = 5,
            sparse_limit: int = 10,
            rerank: bool = True,
    ) -> list[SearchResult]:
        """混合检索：向量路 + FTS5 关键词路 → RRF 融合 → 可选 Rerank 精排。

        若未配置稀疏检索器，回退到纯向量检索。
        """
        if self.sparse_retriever is None:
            logger.warning(
                "sparse_retriever not configured, fallback to dense"
            )
            return await self.retrieve(
                question,
                knowledge_base_id,
                limit,
            )

        query_vector = await self.embedder.embed_texts(
            [question]
        )

        dense_results = await self.qdrant_store.search(
            query_vector=query_vector[0],
            knowledge_base_id=knowledge_base_id,
            limit=max(limit, sparse_limit),
        )

        sparse_results = await self.sparse_retriever.search(
            query=question,
            knowledge_base_id=knowledge_base_id,
            limit=sparse_limit,
        )

        fused: list[FusionItem] = rrf_fuse(
            [
                [
                    (
                        result.document_id,
                        result.chunk_index,
                        result.text,
                    )
                    for result in dense_results
                ],
                [
                    (
                        result.document_id,
                        result.chunk_id,
                        result.text,
                    )
                    for result in sparse_results
                ],
            ],
            limit=limit,
        )

        logger.info(
            "hybrid retrieval: dense=%d, sparse=%d, fused=%d",
            len(dense_results),
            len(sparse_results),
            len(fused),
        )

        if rerank and self.reranker is not None:
            fused = self._rerank_fused(question, fused)

        return [
            SearchResult(
                document_id=item.document_id,
                chunk_index=item.chunk_index,
                text=item.text,
                score=item.score,
            )
            for item in fused
        ]

    def _rerank_fused(
            self,
            question: str,
            fused: list[FusionItem],
    ) -> list[FusionItem]:
        """交叉编码器精排：按 relevance_score 降序重建 FusionItem。"""
        reranked = self.reranker.rerank(
            query=question,
            documents=[item.text for item in fused],
            top_n=len(fused),
        )

        return [
            FusionItem(
                document_id=fused[item.index].document_id,
                chunk_index=fused[item.index].chunk_index,
                text=item.text,
                score=item.relevance_score,
            )
            for item in reranked
        ]
