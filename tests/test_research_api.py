from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.research import ResearchPlan

client = TestClient(app)


@pytest.mark.parametrize("topic", ["", "   "])
def test_research_plan_rejects_empty_topic(topic: str) -> None:
    response = client.post(
        "/api/v1/research/plan",
        json={"topic": topic},
    )

    assert response.status_code == 422


def test_research_plan_returns_mocked_plan(monkeypatch) -> None:
    plan = ResearchPlan(
        topic="Agentic RAG",
        objective="比较传统 RAG 与 Agentic RAG",
        sub_questions=[
            "传统 RAG 的工作流程是什么？",
            "Agentic RAG 增加了哪些决策能力？",
        ],
        search_queries=[
            "traditional RAG workflow",
            "Agentic RAG architecture",
        ],
    )
    mock_generate_plan = AsyncMock(return_value=plan)

    monkeypatch.setattr(
        "app.api.routes.research.generate_research_plan",
        mock_generate_plan,
    )

    response = client.post(
        "/api/v1/research/plan",
        json={"topic": "   Agentic RAG   "},
    )

    assert response.status_code == 200
    assert response.json() == plan.model_dump()
    mock_generate_plan.assert_awaited_once_with("Agentic RAG")