import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.document_retriever import DocumentRetriever
from app.services.qdrant_store import SearchResult


def test_retrieve_returns_search_results() -> None:
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
                )
            ]
        )

        retriever = DocumentRetriever(
            embedder=embedder,
            qdrant_store=qdrant_store,
        )

        results = await retriever.retrieve(
            question="什么是 RAG？",
            knowledge_base_id=1,
        )

        assert len(results) == 1
        assert results[0].text == "RAG 是检索增强生成"
        assert results[0].score == 0.85
        embedder.embed_texts.assert_awaited_once_with(
            ["什么是 RAG？"]
        )
        qdrant_store.search.assert_awaited_once_with(
            query_vector=[0.1, 0.2, 0.3],
            knowledge_base_id=1,
            limit=5,
        )

    asyncio.run(run_test())





