from functools import lru_cache

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import get_settings

@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    settings = get_settings()

    return AsyncQdrantClient(
        url=settings.qdrant_url,
    )


@dataclass(frozen=True)
class SearchResult:
    document_id: int | None
    chunk_index: int | None
    text: str
    score: float



class QdrantStore:
    def __init__(
            self,
            client: AsyncQdrantClient,
            collection_name: str,
            vector_size: int,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.vector_size = vector_size

    async def ensure_collection(self) -> None:
        collections = await self.client.get_collections()

        collection_names = {
            collection.name
            for collection in collections.collections
        }

        if self.collection_name not in collection_names:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert_chunks(
            self,
            document_id: int,
            knowledge_base_id: int,
            chunks: list[str],
            vectors: list[list[float]],
    ) -> int:
        points = [
            PointStruct(
                id=(
                        document_id * 100000
                        + chunk_index
                ),
                vector=vectors[chunk_index],
                payload={
                    "document_id": document_id,
                    "knowledge_base_id": knowledge_base_id,
                    "chunk_index": chunk_index,
                    "text": chunk,
                },
            )
            for chunk_index, chunk in enumerate(chunks)
        ]

        await self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        return len(points)

    async def delete_document_points(
            self,
            document_id: int,
    ) -> None:
        collections = await self.client.get_collections()

        collection_names = {
            collection.name
            for collection in collections.collections
        }

        if self.collection_name not in collection_names:
            return

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(
                            value=document_id
                        ),
                    )
                ]
            ),
        )

    async def delete_knowledge_base_points(
            self,
            knowledge_base_id: int,
    ) -> None:
        collections = await self.client.get_collections()

        collection_names = {
            collection.name
            for collection in collections.collections
        }

        if self.collection_name not in collection_names:
            return

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="knowledge_base_id",
                        match=MatchValue(
                            value=knowledge_base_id
                        ),
                    )
                ]
            ),
        )

    async def search(
            self,
            query_vector: list[float],
            knowledge_base_id: int,
            limit: int = 5,
    ) -> list[SearchResult]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="knowledge_base_id",
                        match=MatchValue(
                            value=knowledge_base_id
                        ),
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
        )

        results = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                SearchResult(
                    document_id=payload.get("document_id"),
                    chunk_index=payload.get("chunk_index"),
                    text=payload.get("text", ""),
                    score=point.score,
                )
            )

        return results