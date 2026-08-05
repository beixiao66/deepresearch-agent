from app.services.document_embedder import DocumentEmbedder
from app.services.qdrant_store import QdrantStore, SearchResult


class DocumentRetriever:
    def __init__(
            self,
            embedder: DocumentEmbedder,
            qdrant_store: QdrantStore,
    ) -> None:
        self.embedder = embedder
        self.qdrant_store = qdrant_store

    async def retrieve(
            self,
            question: str,
            knowledge_base_id: int,
            limit: int = 5,
    ) -> list[SearchResult]:
        query_vector = await self.embedder.embed_texts(
            [question]
        )

        return await self.qdrant_store.search(
            query_vector=query_vector[0],
            knowledge_base_id=knowledge_base_id,
            limit=limit,
        )