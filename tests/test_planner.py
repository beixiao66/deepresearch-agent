import asyncio
from unittest.mock import AsyncMock

from langchain_core.messages import HumanMessage, SystemMessage

from app.schemas.research import ResearchPlan
from app.services.planner import generate_research_plan


def test_generate_research_plan_sends_expected_messages(
        monkeypatch,
) -> None:
    expected_plan = ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )

    async def fake_generate(topic, counters=None):
        return expected_plan

    monkeypatch.setattr(
        "app.services.planner._generate_plan",
        fake_generate,
    )

    result = asyncio.run(
        generate_research_plan("Agentic RAG")
    )

    assert result == expected_plan
