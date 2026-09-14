import asyncio
from unittest.mock import AsyncMock

from langchain_core.messages import HumanMessage, SystemMessage

from app.schemas.research import ResearchPlan
from app.services.planner import generate_research_plan


def build_plan() -> ResearchPlan:
    return ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )


def test_generate_research_plan_sends_expected_messages(
        monkeypatch,
) -> None:
    expected_plan = build_plan()

    async def fake_generate(topic, counters=None, user_context=None):
        return expected_plan

    monkeypatch.setattr(
        "app.services.planner._generate_plan",
        fake_generate,
    )

    result = asyncio.run(
        generate_research_plan("Agentic RAG")
    )

    assert result == expected_plan


def test_generate_research_plan_forwards_user_context(
        monkeypatch,
) -> None:
    """planner 必须把 user_context 透传给 llm.py，且形参要接得住。"""
    expected_plan = build_plan()
    mock_generate = AsyncMock(return_value=expected_plan)
    monkeypatch.setattr(
        "app.services.planner._generate_plan",
        mock_generate,
    )

    result = asyncio.run(generate_research_plan(
        "Agentic RAG",
        None,
        user_context="用户偏好：简洁",
    ))

    assert result == expected_plan
    assert (
        mock_generate.await_args.kwargs["user_context"]
        == "用户偏好：简洁"
    )
