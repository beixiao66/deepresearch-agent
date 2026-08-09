import asyncio
from unittest.mock import AsyncMock

import pytest
import httpx

from fastapi.testclient import TestClient

from openai import AuthenticationError

from app.main import app
from app.schemas.research import ResearchPlan
from app.schemas.research_report import ResearchReport, ResearchRequest

client = TestClient(app)


@pytest.mark.parametrize("topic", ["", "   "])
def test_research_rejects_empty_topic(topic: str) -> None:
    response = client.post(
        "/api/v1/research",
        json={"topic": topic},
    )
    assert response.status_code == 422


def test_research_returns_mocked_report(monkeypatch) -> None:
    async def fake_stream(request, task_repository):
        yield "data: {\"type\": \"task_created\", \"task_id\": 1}\n\n"
        yield "data: {\"type\": \"awaiting_approval\"}\n\n"

    monkeypatch.setattr(
        "app.api.routes.research.stream_start_research",
        fake_stream,
    )

    response = client.post(
        "/api/v1/research",
        json={"topic": "   Agentic RAG   "},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert "task_created" in response.text
    assert "awaiting_approval" in response.text
