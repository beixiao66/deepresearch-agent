from unittest.mock import AsyncMock, Mock

import pytest

from fastapi.testclient import TestClient

from app.api.dependencies import get_document_retriever
from app.main import app
from app.services.qdrant_store import SearchResult


def create_client_with_retriever(retriever: Mock) -> TestClient:
    app.dependency_overrides[
        get_document_retriever
    ] = lambda: retriever

    return TestClient(app)


def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()


def test_search_returns_200_with_results() -> None:
    retriever = Mock()
    retriever.retrieve = AsyncMock(
        return_value=[
            SearchResult(
                document_id=1,
                chunk_index=3,
                text="RAG 是检索增强生成",
                score=0.85,
            ),
            SearchResult(
                document_id=1,
                chunk_index=4,
                text="RAG 结合信息检索和文本生成",
                score=0.72,
            ),
        ]
    )

    client = create_client_with_retriever(retriever)
    response = client.post(
        "/api/v1/knowledge-bases/1/search",
        json={"question": "什么是 RAG？"},
    )
    clear_dependency_overrides()

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["document_id"] == 1
    assert data["results"][0]["chunk_index"] == 3
    assert data["results"][0]["text"] == "RAG 是检索增强生成"
    assert data["results"][0]["score"] == 0.85

    retriever.retrieve.assert_awaited_once_with(
        question="什么是 RAG？",
        knowledge_base_id=1,
    )


def test_search_empty_results_returns_empty_list() -> None:
    retriever = Mock()
    retriever.retrieve = AsyncMock(return_value=[])

    client = create_client_with_retriever(retriever)
    response = client.post(
        "/api/v1/knowledge-bases/1/search",
        json={"question": "不存在的内容"},
    )
    clear_dependency_overrides()

    assert response.status_code == 200
    assert response.json() == {"results": []}


@pytest.mark.parametrize(
    "knowledge_base_id, question",
    [
        (0, "什么是 RAG？"),
        (-1, "什么是 RAG？"),
    ],
)
def test_search_rejects_invalid_knowledge_base_id(
        knowledge_base_id: int,
        question: str,
) -> None:
    retriever = Mock()
    retriever.retrieve = AsyncMock()

    client = create_client_with_retriever(retriever)
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/search",
        json={"question": question},
    )
    clear_dependency_overrides()

    assert response.status_code == 422
    retriever.retrieve.assert_not_awaited()


@pytest.mark.parametrize("question", ["", "   "])
def test_search_rejects_empty_question(question: str) -> None:
    retriever = Mock()
    retriever.retrieve = AsyncMock()

    client = create_client_with_retriever(retriever)
    response = client.post(
        "/api/v1/knowledge-bases/1/search",
        json={"question": question},
    )
    clear_dependency_overrides()

    assert response.status_code == 422
    retriever.retrieve.assert_not_awaited()
