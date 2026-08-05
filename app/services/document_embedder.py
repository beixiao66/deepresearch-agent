from functools import lru_cache

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
    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def embed_texts(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        response = self.client.embeddings.create(
            model="text-embedding-v4",
            input=texts,
        )

        return [
            item.embedding
            for item in response.data
        ]
