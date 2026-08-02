import asyncio
from unittest.mock import AsyncMock, Mock

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

    mock_planner = Mock()
    mock_planner.ainvoke = AsyncMock(return_value=expected_plan)

    monkeypatch.setattr(
        "app.services.planner.get_planner",
        lambda: mock_planner,
    )

    result = asyncio.run(
        generate_research_plan("Agentic RAG")
    )

    assert result == expected_plan
    mock_planner.ainvoke.assert_awaited_once()

    messages = mock_planner.ainvoke.await_args.args[0]

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "研究主题：Agentic RAG"