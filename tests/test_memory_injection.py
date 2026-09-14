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


def test_plan_node_works_with_real_planner(monkeypatch) -> None:
    """回归：只 mock LLM 层，走 _plan_research → planner → llm 的真实调用链。

    之前 planner.generate_research_plan 漏了 user_context 形参，而
    research_graph 传了它，导致创建研究稳定抛 TypeError。上面两个用例
    把 research_graph.generate_research_plan 整体换成 AsyncMock
    （接受任意参数），因此掩盖了签名不一致——这个用例专门防这一类问题。
    """
    from langchain_core.messages import AIMessage

    from app.schemas.research import ResearchPlan

    plan = ResearchPlan(
        topic="RAG",
        objective="研究 RAG",
        sub_questions=["RAG 是什么？"],
        search_queries=["RAG"],
    )

    captured: dict = {}

    class FakeStructured:
        async def ainvoke(self, messages):
            captured["messages"] = messages
            return {"raw": AIMessage(content=""), "parsed": plan}

    mock_llm = Mock()
    mock_llm.with_structured_output = Mock(
        return_value=FakeStructured()
    )
    monkeypatch.setattr(
        "app.services.llm.get_llm",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "app.services.research_graph.get_preferences",
        AsyncMock(return_value={
            "report_style": "concise",
            "report_language": "zh",
        }),
    )
    monkeypatch.setattr(
        "app.services.research_graph.get_research_history",
        AsyncMock(return_value=[]),
    )

    result = asyncio.run(_plan_research({
        "question": "RAG",
        "knowledge_base_id": 1,
        "use_web_search": False,
    }))

    assert result["plan"] == plan
    # 偏好经 user_context 一路传到 system prompt
    assert "concise" in captured["messages"][0].content
