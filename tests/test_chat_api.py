import httpx
import pytest

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from unittest.mock import ANY, AsyncMock
from fastapi.testclient import TestClient

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


def test_chat_returns_conversation_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.chat.send_message",
        AsyncMock(return_value=("RAG 是检索增强生成。", "abc123")),
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "什么是 RAG？"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "RAG 是检索增强生成。",
        "model": "qwen-plus",
        "conversation_id": "abc123",
    }


def test_chat_passes_conversation_id(monkeypatch) -> None:
    mock_send = AsyncMock(return_value=("回答", "abc123"))
    monkeypatch.setattr(
        "app.api.routes.chat.send_message",
        mock_send,
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "追问", "conversation_id": "abc123"},
    )

    assert response.status_code == 200
    # 路由调用 send_message(question, conversation_id, session)，session 由依赖注入
    mock_send.assert_awaited_once_with("追问", "abc123", ANY)


def test_chat_maps_authentication_error_to_502(monkeypatch) -> None:
    request = httpx.Request(method="POST", url="https://model.example.com/chat")
    upstream_response = httpx.Response(status_code=401, request=request)
    authentication_error = AuthenticationError(
        "Invalid API key", response=upstream_response, body=None
    )

    monkeypatch.setattr(
        "app.api.routes.chat.send_message",
        AsyncMock(side_effect=authentication_error),
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "测试鉴权异常"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "MODEL_AUTHENTICATION_FAILED",
            "message": "模型服务认证失败，请联系管理员检查配置",
        }
    }


def test_chat_maps_rate_limit_error_to_503(monkeypatch) -> None:
    request = httpx.Request(method="POST", url="https://model.example.com/chat")
    upstream_response = httpx.Response(status_code=429, request=request)
    rate_limit_error = RateLimitError(
        "Rate limit exceeded", response=upstream_response, body=None
    )

    monkeypatch.setattr(
        "app.api.routes.chat.send_message",
        AsyncMock(side_effect=rate_limit_error),
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "测试限流异常"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "MODEL_RATE_LIMITED",
            "message": "模型服务当前繁忙，请稍后重试",
        }
    }


@pytest.mark.parametrize(
    ("model_error", "expected_status", "expected_code", "expected_message"),
    [
        (
            APITimeoutError(
                request=httpx.Request("POST", "https://model.example.com/chat")
            ),
            504,
            "MODEL_TIMEOUT",
            "模型服务响应超时，请稍后重试",
        ),
        (
            APIConnectionError(
                request=httpx.Request("POST", "https://model.example.com/chat")
            ),
            503,
            "MODEL_CONNECTION_FAILED",
            "暂时无法连接模型服务，请稍后重试",
        ),
        (
            APIStatusError(
                "Upstream model error",
                response=httpx.Response(
                    status_code=500,
                    request=httpx.Request(
                        "POST", "https://model.example.com/chat"
                    ),
                ),
                body=None,
            ),
            502,
            "MODEL_SERVICE_ERROR",
            "模型服务处理失败，请稍后重试",
        ),
    ],
)
def test_chat_maps_model_errors(
    monkeypatch,
    model_error: Exception,
    expected_status: int,
    expected_code: str,
    expected_message: str,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.chat.send_message",
        AsyncMock(side_effect=model_error),
    )

    response = client.post(
        "/api/v1/chat",
        json={"question": "测试模型服务异常"},
    )

    assert response.status_code == expected_status
    assert response.json() == {
        "error": {
            "code": expected_code,
            "message": expected_message,
        }
    }


def test_list_conversations_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.chat.list_conversations",
        AsyncMock(return_value=[]),
    )

    response = client.get("/api/v1/chat/conversations")

    assert response.status_code == 200
    assert response.json() == []


def test_delete_conversation_returns_204(monkeypatch) -> None:
    mock_delete = AsyncMock()
    monkeypatch.setattr(
        "app.api.routes.chat.delete_conversation",
        mock_delete,
    )

    response = client.delete("/api/v1/chat/conversations/abc123")

    assert response.status_code == 204
    # session 由依赖注入，只断言会话 id 透传
    mock_delete.assert_awaited_once_with("abc123", ANY)


def test_delete_missing_conversation_returns_404(monkeypatch) -> None:
    from app.core.exceptions import ConversationNotFoundError

    monkeypatch.setattr(
        "app.api.routes.chat.delete_conversation",
        AsyncMock(side_effect=ConversationNotFoundError("abc123")),
    )

    response = client.delete("/api/v1/chat/conversations/abc123")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "CONVERSATION_NOT_FOUND",
            "message": "会话不存在",
        }
    }
