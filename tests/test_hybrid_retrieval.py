import asyncio

import pytest

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.services.sparse_indexer import SparseIndexer
from app.services.sparse_retriever import (
    SparseRetriever,
    build_match_query,
)
from app.services.rrf import rrf_fuse


def test_build_match_query_escapes_special_chars() -> None:
    assert (
        build_match_query("step-by-step")
        == '"step by step"'
    )
    assert (
        build_match_query("RAG 是什么")
        == '"RAG" AND "是什么"'
    )
    assert '"("' not in build_match_query(
        "Chunking (split)"
    )


@pytest.fixture
def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
    )
    Session = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    yield Session
    import asyncio as _asyncio
    _asyncio.run(engine.dispose())


def test_sparse_index_and_search_bm25(session_factory) -> None:
    async def run_test() -> None:
        async with session_factory() as session:
            indexer = SparseIndexer(session)
            await indexer.ensure_table()
            await indexer.index_chunks(
                document_id=10,
                knowledge_base_id=3,
                chunks=[
                    "RAG 是检索增强生成的缩写",
                    "向量数据库存储向量和文本",
                    "HTTP 429 表示请求太多",
                ],
            )

            retriever = SparseRetriever(session)
            results = await retriever.search(
                query="RAG",
                knowledge_base_id=3,
                limit=5,
            )

            assert len(results) == 1
            assert results[0].document_id == 10
            assert "RAG" in results[0].text

    asyncio.run(run_test())


def test_sparse_search_filters_by_knowledge_base(
        session_factory,
) -> None:
    async def run_test() -> None:
        async with session_factory() as session:
            indexer = SparseIndexer(session)
            await indexer.ensure_table()
            await indexer.index_chunks(
                document_id=1,
                knowledge_base_id=1,
                chunks=["RAG 是检索增强生成"],
            )
            await indexer.index_chunks(
                document_id=2,
                knowledge_base_id=2,
                chunks=["RAG 是检索增强生成"],
            )

            retriever = SparseRetriever(session)
            results = await retriever.search(
                query="RAG",
                knowledge_base_id=1,
                limit=5,
            )

            assert len(results) == 1
            assert results[0].document_id == 1

    asyncio.run(run_test())


def test_sparse_delete_document(session_factory) -> None:
    async def run_test() -> None:
        async with session_factory() as session:
            indexer = SparseIndexer(session)
            await indexer.ensure_table()
            await indexer.index_chunks(
                document_id=5,
                knowledge_base_id=3,
                chunks=["LangGraph 是图编排框架"],
            )

            await indexer.delete_document(5)

            retriever = SparseRetriever(session)
            results = await retriever.search(
                query="LangGraph",
                knowledge_base_id=3,
                limit=5,
            )
            assert results == []

    asyncio.run(run_test())


def test_rrf_fuses_two_ranked_lists() -> None:
    vector_ranked = [
        (1, 0, "向量路第一"),
        (2, 0, "向量路第二"),
        (3, 0, "向量路第三"),
    ]
    sparse_ranked = [
        (2, 0, "稀疏路第一"),
        (1, 0, "稀疏路第二"),
    ]

    fused = rrf_fuse([vector_ranked, sparse_ranked], limit=3)

    assert len(fused) == 3
    # (1,0) 排名 1+2； (2,0) 排名 2+1 → 两个分数相同，但 (1,0) 先出现
    assert fused[0].document_id == 1
    assert fused[1].document_id == 2
    assert fused[2].document_id == 3
