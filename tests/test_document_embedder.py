import asyncio
from unittest.mock import Mock

from app.services.document_embedder import DocumentEmbedder


def test_embed_texts_batches_over_10_items() -> None:
    def fake_create(*args, **kwargs):
        items = kwargs["input"]
        return Mock(
            data=[
                Mock(embedding=[float(index)])
                for index in range(len(items))
            ]
        )

    client = Mock()
    client.embeddings.create = Mock(
        side_effect=fake_create,
    )

    embedder = DocumentEmbedder(client=client)

    texts = [f"第{i}段" for i in range(25)]

    vectors = asyncio.run(
        embedder.embed_texts(texts)
    )

    assert len(vectors) == 25
    assert client.embeddings.create.call_count == 3

    batch_sizes = [
        len(call.kwargs["input"])
        for call in client.embeddings.create.call_args_list
    ]
    assert batch_sizes == [10, 10, 5]


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
