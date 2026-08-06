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
    plan = ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )
    report = ResearchReport(
        topic="Agentic RAG",
        plan=plan,
        sources=[],
        answer="Agentic RAG 是……",
    )

    mock_run = AsyncMock(return_value=report)
    monkeypatch.setattr(
        "app.api.routes.research.run_research",
        mock_run,
    )

    response = client.post(
        "/api/v1/research",
        json={"topic": "   Agentic RAG   "},
    )

    assert response.status_code == 200
    assert response.json() == report.model_dump()
    mock_run.assert_awaited_once()
