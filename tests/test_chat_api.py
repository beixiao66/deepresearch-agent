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