from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from app.main import app

client = TestClient(app)

def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_rejects_empty_question() -> None:
    response = client.post(
        "/api/v1/chat",
        json={"question": ""},
    )
    assert response.status_code == 422


def test_chat_rejects_blank_question() -> None:
    response = client.post(
        "/api/v1/chat",
        json={"question": "   "},
    )

    assert response.status_code == 422


def test_chat_rejects_question_over_max_length() -> None:
    response = client.post(
        "/api/v1/chat",
        json={"question": "a" * 2001},
    )

    assert response.status_code == 422


def test_chat_returns_mocked_model_response(monkeypatch) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="RAG 是检索增强生成。")
    )

    monkeypatch.setattr(
        "app.api.routes.chat.get_llm",
        lambda: mock_llm,
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "什么是 RAG？"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "RAG 是检索增强生成。",
        "model": "qwen-plus",
    }
    mock_llm.ainvoke.assert_awaited_once()

def test_chat_sends_system_and_user_messages(monkeypatch) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="测试回答")
    )

    monkeypatch.setattr(
        "app.api.routes.chat.get_llm",
        lambda: mock_llm,
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "用户的测试问题"},
    )

    assert response.status_code == 200

    mock_llm.ainvoke.assert_awaited_once()
    messages = mock_llm.ainvoke.await_args.args[0]

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "用户的测试问题"