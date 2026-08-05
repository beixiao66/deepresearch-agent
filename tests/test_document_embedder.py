import asyncio
from unittest.mock import Mock

from app.services.document_embedder import DocumentEmbedder


def test_embed_texts_returns_vectors() -> None:
    response_data = [
        Mock(embedding=[0.1, 0.2, 0.3]),
        Mock(embedding=[0.4, 0.5, 0.6]),
    ]
    response = Mock(data=response_data)

    client = Mock()
    client.embeddings.create = Mock(
        return_value=response
    )

    embedder = DocumentEmbedder(client=client)

    vectors = asyncio.run(
        embedder.embed_texts(
            ["第一段文本", "第二段文本"]
        )
    )

    assert len(vectors) == 2
    assert vectors[0] == [0.1, 0.2, 0.3]
    assert vectors[1] == [0.4, 0.5, 0.6]
    client.embeddings.create.assert_called_once_with(
        model="text-embedding-v4",
        input=["第一段文本", "第二段文本"],
    )
