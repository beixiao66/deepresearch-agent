# tests/test_memory_injection.py
import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.research_graph import _plan_research


def test_plan_node_injects_user_context(monkeypatch) -> None:
    from app.schemas.research import ResearchPlan

    plan = ResearchPlan(
        topic="RAG",
        objective="研究 RAG",
        sub_questions=["RAG 是什么？"],
        search_queries=["RAG"],
    )

    mock_generate = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "app.services.research_graph.generate_research_plan",
        mock_generate,
    )
    monkeypatch.setattr(
        "app.services.research_graph.get_preferences",
        AsyncMock(return_value={
            "report_style": "concise",
            "report_language": "en",
        }),
    )
    monkeypatch.setattr(
        "app.services.research_graph.get_research_history",
        AsyncMock(return_value=[
            {
                "topic": "Agentic RAG",
                "task_id": 1,
                "created_at": "2026-08-29T10:00:00+00:00",
                "summary": "摘要",
            }
        ]),
    )

    result = asyncio.run(_plan_research({
        "question": "RAG",
        "knowledge_base_id": 1,
        "use_web_search": False,
    }))

    assert result["plan"] == plan
    assert mock_generate.await_args.kwargs["user_context"] is not None
    context = mock_generate.await_args.kwargs["user_context"]
    assert "concise" in context
    assert "Agentic RAG" in context


def test_plan_node_continues_without_context_on_memory_error(
        monkeypatch,
) -> None:
    from app.schemas.research import ResearchPlan

    plan = ResearchPlan(
        topic="RAG",
        objective="研究 RAG",
        sub_questions=["RAG 是什么？"],
        search_queries=["RAG"],
    )

    mock_generate = AsyncMock(return_value=plan)
    monkeypatch.setattr(
        "app.services.research_graph.generate_research_plan",
        mock_generate,
    )
    monkeypatch.setattr(
        "app.services.research_graph.get_preferences",
        AsyncMock(side_effect=RuntimeError("store down")),
    )
    monkeypatch.setattr(
        "app.services.research_graph.get_research_history",
        AsyncMock(side_effect=RuntimeError("store down")),
    )

    result = asyncio.run(_plan_research({
        "question": "RAG",
        "knowledge_base_id": 1,
        "use_web_search": False,
    }))

    assert result["plan"] == plan
    assert mock_generate.await_args.kwargs["user_context"] is None
