import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.document_indexer import DocumentIndexer
from app.services.document_parser import ParsedDocument
from app.services.document_splitter import TextChunk


def test_index_document_full_pipeline() -> None:
    async def run_test() -> None:
        parser = Mock()
        parser.parse = Mock(
            return_value=ParsedDocument(
                text="第一段\n第二段\n第三段"
            )
        )

        splitter = Mock()
        splitter.split = Mock(
            return_value=[
                TextChunk(text="第一段", chunk_index=0),
                TextChunk(text="第二段", chunk_index=1),
                TextChunk(text="第三段", chunk_index=2),
            ]
        )

        embedder = Mock()
        embedder.embed_texts = AsyncMock(
            return_value=[
                [0.1] * 1024,
                [0.2] * 1024,
                [0.3] * 1024,
            ]
        )

        qdrant_store = Mock()
        qdrant_store.ensure_collection = AsyncMock()
        qdrant_store.upsert_chunks = AsyncMock(
            return_value=3
        )

        indexer = DocumentIndexer(
            parser=parser,
            splitter=splitter,
            embedder=embedder,
            qdrant_store=qdrant_store,
        )

        point_count, chunk_texts = await indexer.index_document(
            storage_path="data/uploads/1/uuid.md",
            file_extension=".md",
            document_id=5,
            knowledge_base_id=1,
        )

        assert point_count == 3
        assert chunk_texts == ["第一段", "第二段", "第三段"]
        parser.parse.assert_called_once_with(
            "data/uploads/1/uuid.md",
            ".md",
        )
        embedder.embed_texts.assert_awaited_once_with(
            ["第一段", "第二段", "第三段"]
        )
        qdrant_store.upsert_chunks.assert_awaited_once_with(
            document_id=5,
            knowledge_base_id=1,
            chunks=["第一段", "第二段", "第三段"],
            vectors=[
                [0.1] * 1024,
                [0.2] * 1024,
                [0.3] * 1024,
            ],
        )

    asyncio.run(run_test())


def test_index_document_rejects_empty_text() -> None:
    async def run_test() -> None:
        parser = Mock()
        parser.parse = Mock(
            return_value=ParsedDocument(text="   ")
        )

        splitter = Mock()
        embedder = Mock()
        embedder.embed_texts = AsyncMock()
        qdrant_store = Mock()
        qdrant_store.upsert_chunks = AsyncMock()

        indexer = DocumentIndexer(
            parser=parser,
            splitter=splitter,
            embedder=embedder,
            qdrant_store=qdrant_store,
        )

        import pytest

        with pytest.raises(ValueError):
            await indexer.index_document(
                storage_path="data/uploads/1/scan.pdf",
                file_extension=".pdf",
                document_id=6,
                knowledge_base_id=1,
            )

        splitter.split.assert_not_called()
        embedder.embed_texts.assert_not_awaited()
        qdrant_store.upsert_chunks.assert_not_awaited()

    asyncio.run(run_test())