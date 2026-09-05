# tests/test_memory_api.py
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_preferences_returns_defaults(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.memory.get_preferences",
        AsyncMock(return_value={
            "report_style": "detailed",
            "report_language": "zh",
        }),
    )

    response = client.get("/api/v1/memory/preferences")

    assert response.status_code == 200
    assert response.json() == {
        "report_style": "detailed",
        "report_language": "zh",
    }


def test_put_preferences_saves_and_returns(monkeypatch) -> None:
    mock_save = AsyncMock()
    monkeypatch.setattr(
        "app.api.routes.memory.save_preferences",
        mock_save,
    )

    response = client.put(
        "/api/v1/memory/preferences",
        json={
            "user_id": 1,
            "report_style": "concise",
            "report_language": "en",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "report_style": "concise",
        "report_language": "en",
    }
    mock_save.assert_awaited_once_with(1, {
        "report_style": "concise",
        "report_language": "en",
    })


def test_put_preferences_rejects_invalid_style(monkeypatch) -> None:
    response = client.put(
        "/api/v1/memory/preferences",
        json={"report_style": "loud", "report_language": "zh"},
    )

    assert response.status_code == 422
