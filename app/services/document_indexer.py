import logging

from app.services.document_embedder import DocumentEmbedder
from app.services.document_parser import DocumentParser
from app.services.document_splitter import DocumentSplitter
from app.services.qdrant_store import QdrantStore

logger = logging.getLogger(__name__)


class DocumentIndexer:
    def __init__(
            self,
            parser: DocumentParser,
            splitter: DocumentSplitter,
            embedder: DocumentEmbedder,
            qdrant_store: QdrantStore,
    ) -> None:
        self.parser = parser
        self.splitter = splitter
        self.embedder = embedder
        self.qdrant_store = qdrant_store

    async def index_document(
            self,
            storage_path: str,
            file_extension: str,
            document_id: int,
            knowledge_base_id: int,
    ) -> int:
        parsed = self.parser.parse(
            storage_path,
            file_extension,
        )

        if not parsed.text.strip():
            raise ValueError(
                "Document contains no extractable text"
            )

        chunks = self.splitter.split(parsed.text)

        if not chunks:
            raise ValueError(
                "Document produced no chunks"
            )

        chunk_texts = [
            chunk.text
            for chunk in chunks
        ]

        vectors = await self.embedder.embed_texts(
            chunk_texts
        )

        await self.qdrant_store.ensure_collection()

        point_count = await self.qdrant_store.upsert_chunks(
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            chunks=chunk_texts,
            vectors=vectors,
        )

        logger.info(
            "Indexed document: document_id=%d, chunks=%d",
            document_id,
            point_count,
        )

        return point_count