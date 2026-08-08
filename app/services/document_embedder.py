from functools import lru_cache

import anyio
from openai import OpenAI

from app.core.config import get_settings


@lru_cache
def get_embedding_client() -> OpenAI:
    settings = get_settings()

    return OpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=settings.dashscope_base_url,
    )


class DocumentEmbedder:
    BATCH_SIZE = 10

    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def _embed_sync(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        vectors: list[list[float]] = []

        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start:start + self.BATCH_SIZE]

            response = self.client.embeddings.create(
                model="text-embedding-v4",
                input=batch,
            )
            vectors.extend(
                item.embedding
                for item in response.data
            )

        return vectors

    async def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return await anyio.to_thread.run_sync(
            self._embed_sync,
            texts,
        )
