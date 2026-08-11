import httpx
import pytest

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
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


def test_chat_maps_authentication_error_to_502(monkeypatch) -> None:
    request = httpx.Request(
        method="POST",
        url="https://model.example.com/chat",
    )
    upstream_response = httpx.Response(
        status_code=401,
        request=request,
    )
    authentication_error = AuthenticationError(
        "Invalid API key",
        response=upstream_response,
        body=None,
    )

    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=authentication_error,
    )

    monkeypatch.setattr(
        "app.api.routes.chat.get_llm",
        lambda: mock_llm,
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
    mock_llm.ainvoke.assert_awaited_once()


def test_chat_maps_rate_limit_error_to_503(monkeypatch) -> None:
    request = httpx.Request(
        method="POST",
        url="https://model.example.com/chat",
    )
    upstream_response = httpx.Response(
        status_code=429,
        request=request,
    )
    rate_limit_error = RateLimitError(
        "Rate limit exceeded",
        response=upstream_response,
        body=None,
    )

    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=rate_limit_error,
    )

    monkeypatch.setattr(
        "app.api.routes.chat.get_llm",
        lambda: mock_llm,
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
    mock_llm.ainvoke.assert_awaited_once()

@pytest.mark.parametrize(
    (
        "model_error",
        "expected_status",
        "expected_code",
        "expected_message",
    ),
    [
        (
            APITimeoutError(
                request=httpx.Request(
                    "POST",
                    "https://model.example.com/chat",
                )
            ),
            504,
            "MODEL_TIMEOUT",
            "模型服务响应超时，请稍后重试",
        ),
        (
            APIConnectionError(
                request=httpx.Request(
                    "POST",
                    "https://model.example.com/chat",
                )
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
                        "POST",
                        "https://model.example.com/chat",
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
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(side_effect=model_error)

    monkeypatch.setattr(
        "app.api.routes.chat.get_llm",
        lambda: mock_llm,
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
    mock_llm.ainvoke.assert_awaited_once()