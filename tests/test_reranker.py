import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.document_retriever import DocumentRetriever
from app.services.qdrant_store import SearchResult
from app.services.reranker import Reranker, RerankedItem
from app.services.sparse_retriever import SparseResult


def test_rerank_returns_sorted_results() -> None:
    client = Mock()
    client.post = Mock(
        return_value={
            "results": [
                {"index": 1, "relevance_score": 0.91},
                {"index": 0, "relevance_score": 0.28},
            ]
        }
    )

    reranker = Reranker(client=client)

    documents = ["量子计算前沿", "RAG 是检索增强生成"]
    results = reranker.rerank(
        query="RAG 是什么",
        documents=documents,
        top_n=2,
    )

    assert len(results) == 2
    assert results[0].index == 1
    assert results[0].relevance_score == 0.91
    assert results[0].text == "RAG 是检索增强生成"

    client.post.assert_called_once()
    body = client.post.call_args.kwargs["body"]
    assert body["model"] == "qwen3-rerank"
    assert body["query"] == "RAG 是什么"
    assert body["documents"] == documents


def test_rerank_empty_documents_returns_empty() -> None:
    client = Mock()
    reranker = Reranker(client=client)

    results = reranker.rerank(
        query="RAG 是什么",
        documents=[],
    )

    assert results == []
    client.post.assert_not_called()


def test_retrieve_hybrid_with_rerank_reorders_results() -> None:
    async def run_test() -> None:
        embedder = Mock()
        embedder.embed_texts = AsyncMock(
            return_value=[[0.1, 0.2, 0.3]]
        )

        qdrant_store = Mock()
        qdrant_store.search = AsyncMock(
            return_value=[
                SearchResult(
                    document_id=1,
                    chunk_index=0,
                    text="RAG 是检索增强生成",
                    score=0.85,
                ),
                SearchResult(
                    document_id=2,
                    chunk_index=0,
                    text="HTTP 429 表示请求太多",
                    score=0.60,
                ),
            ]
        )

        sparse_retriever = Mock()
        sparse_retriever.search = AsyncMock(
            return_value=[
                SparseResult(
                    document_id=2,
                    chunk_id=0,
                    text="HTTP 429 表示请求太多",
                    score=12.5,
                ),
            ]
        )

        # 融合后实际顺序是 [doc2, doc1]（doc2 向量第2+稀疏第1，RRF 分更高）
        # Rerank 反转：把融合后第二的 doc1（index=1）提到第一
        reranker = Mock()
        reranker.rerank = Mock(
            return_value=[
                RerankedItem(
                    index=1,
                    relevance_score=0.92,
                    text="RAG 是检索增强生成",
                ),
                RerankedItem(
                    index=0,
                    relevance_score=0.55,
                    text="HTTP 429 表示请求太多",
                ),
            ]
        )

        retriever = DocumentRetriever(
            embedder=embedder,
            qdrant_store=qdrant_store,
            sparse_retriever=sparse_retriever,
            reranker=reranker,
        )

        results = await retriever.retrieve_hybrid(
            question="HTTP 429 是什么？",
            knowledge_base_id=1,
            limit=2,
        )

        # 重排后 doc1 提到第一，分数换成 relevance_score
        assert results[0].document_id == 1
        assert results[0].text == "RAG 是检索增强生成"
        assert results[0].score == 0.92
        assert results[1].document_id == 2
        reranker.rerank.assert_called_once()

    asyncio.run(run_test())


def test_retrieve_hybrid_skips_rerank_when_not_configured() -> None:
    async def run_test() -> None:
        embedder = Mock()
        embedder.embed_texts = AsyncMock(
            return_value=[[0.1, 0.2, 0.3]]
        )

        qdrant_store = Mock()
        qdrant_store.search = AsyncMock(
            return_value=[
                SearchResult(
                    document_id=1,
                    chunk_index=0,
                    text="RAG 是检索增强生成",
                    score=0.85,
                ),
            ]
        )

        sparse_retriever = Mock()
        sparse_retriever.search = AsyncMock(
            return_value=[
                SparseResult(
                    document_id=2,
                    chunk_id=0,
                    text="HTTP 429 表示请求太多",
                    score=12.5,
                ),
            ]
        )

        retriever = DocumentRetriever(
            embedder=embedder,
            qdrant_store=qdrant_store,
            sparse_retriever=sparse_retriever,
            reranker=None,
        )

        results = await retriever.retrieve_hybrid(
            question="HTTP 429 是什么？",
            knowledge_base_id=1,
            limit=2,
        )

        assert len(results) == 2

    asyncio.run(run_test())
