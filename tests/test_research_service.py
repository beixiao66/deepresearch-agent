import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.research import ResearchPlan
from app.schemas.research_report import ResearchReport, ResearchRequest
from app.services.research import (
    approve_research,
    get_research_graph,
    start_research,
)
from app.services.research_graph import (
    _report,
    _should_continue,
    build_research_graph,
)


def test_build_research_graph_has_expected_structure() -> None:
    graph = build_research_graph()

    nodes = graph.get_graph().nodes
    edges = graph.get_graph().edges

    assert "plan" in nodes
    assert "review" in nodes
    assert "retrieve" in nodes
    assert "next_queries" in nodes
    assert "report" in nodes
    assert "__start__" in nodes
    assert "__end__" in nodes

    plain_edges = [
        (edge.source, edge.target)
        for edge in edges
        if not edge.conditional
    ]
    assert ("__start__", "plan") in plain_edges
    assert ("plan", "review") in plain_edges
    assert ("review", "retrieve") in plain_edges
    assert ("next_queries", "retrieve") in plain_edges
    assert ("report", "__end__") in plain_edges

    conditional_edges = [
        (edge.source, edge.target)
        for edge in edges
        if edge.conditional
    ]
    assert ("retrieve", "report") in conditional_edges
    assert ("retrieve", "next_queries") in conditional_edges


def test_start_research_pauses_at_plan_review(
        monkeypatch,
) -> None:
    plan = ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )

    fake_graph = Mock()
    fake_graph.ainvoke = AsyncMock(
        return_value={"plan": plan}
    )
    monkeypatch.setattr(
        "app.services.research.get_research_graph",
        lambda: fake_graph,
    )

    request = ResearchRequest(
        topic="Agentic RAG",
        knowledge_base_id=1,
    )

    from app.models.research_task import (
        ResearchTask,
        ResearchTaskStatus,
    )

    task = ResearchTask(
        id=1,
        topic="Agentic RAG",
        knowledge_base_id=1,
        status=ResearchTaskStatus.PENDING.value,
    )

    task_repository = Mock()
    task_repository.create = AsyncMock(return_value=task)
    task_repository.update_status = AsyncMock()
    task_repository.save_plan = AsyncMock()
    task_repository.session = Mock()
    task_repository.session.commit = AsyncMock()

    report = asyncio.run(
        start_research(request, task_repository)
    )

    assert report.topic == "Agentic RAG"
    assert report.plan == plan
    assert report.sources == []
    fake_graph.ainvoke.assert_awaited_once()
    task_repository.save_plan.assert_awaited_once()


def test_approve_research_completes_report(
        monkeypatch,
) -> None:
    plan = ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )

    fake_graph = Mock()
    fake_graph.ainvoke = AsyncMock(
        return_value={
            "plan": plan,
            "sources": [
                {
                    "document_id": 1,
                    "chunk_index": 2,
                    "text": "Agentic RAG 是……",
                    "score": 0.9,
                    "query": "Agentic RAG",
                }
            ],
            "answer": "Agentic RAG 是……",
        }
    )
    monkeypatch.setattr(
        "app.services.research.get_research_graph",
        lambda: fake_graph,
    )

    from app.models.research_task import (
        ResearchTask,
        ResearchTaskStatus,
    )

    task = ResearchTask(
        id=1,
        topic="Agentic RAG",
        knowledge_base_id=1,
        status=ResearchTaskStatus.AWAITING_APPROVAL.value,
    )

    task_repository = Mock()
    task_repository.get_by_id = AsyncMock(
        return_value=task
    )
    task_repository.update_status = AsyncMock()
    task_repository.save_report = AsyncMock()
    task_repository.session = Mock()
    task_repository.session.commit = AsyncMock()

    report = asyncio.run(
        approve_research(1, True, task_repository)
    )

    assert isinstance(report, ResearchReport)
    assert report.plan == plan
    assert len(report.sources) == 1
    assert report.answer == "Agentic RAG 是……"
    fake_graph.ainvoke.assert_awaited_once()


def test_approve_research_rejected_marks_failed(
        monkeypatch,
) -> None:
    plan = ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )

    fake_graph = Mock()
    fake_graph.ainvoke = AsyncMock(
        return_value={"plan": plan}
    )
    monkeypatch.setattr(
        "app.services.research.get_research_graph",
        lambda: fake_graph,
    )

    from app.models.research_task import (
        ResearchTask,
        ResearchTaskStatus,
    )

    task = ResearchTask(
        id=1,
        topic="Agentic RAG",
        knowledge_base_id=1,
        status=ResearchTaskStatus.AWAITING_APPROVAL.value,
    )

    task_repository = Mock()
    task_repository.get_by_id = AsyncMock(
        return_value=task
    )
    task_repository.update_status = AsyncMock()
    task_repository.session = Mock()
    task_repository.session.commit = AsyncMock()

    report = asyncio.run(
        approve_research(1, False, task_repository)
    )

    assert report.sources == []
    task_repository.update_status.assert_awaited()


def test_report_without_sources_does_not_call_llm(
        monkeypatch,
) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock()
    monkeypatch.setattr(
        "app.services.research_graph.get_llm",
        lambda: mock_llm,
    )

    result = asyncio.run(
        _report({
            "question": "什么是 RAG？",
            "sources": [],
        })
    )

    assert "暂无足够资料" in result["answer"]
    assert "未使用模型自身知识" in result["answer"]
    mock_llm.ainvoke.assert_not_awaited()


def test_should_continue_enough_sources_reports() -> None:
    assert _should_continue(
        {
            "sources": [
                {"text": "a", "score": 0.8},
                {"text": "b", "score": 0.7},
                {"text": "c", "score": 0.6},
            ]
        }
    ) == "report"


def test_should_continue_low_quality_sources_continue() -> None:
    assert _should_continue(
        {
            "sources": [
                {"text": "a", "score": 0.1},
                {"text": "b", "score": 0.1},
                {"text": "c", "score": 0.1},
            ],
            "retrieval_round": 1,
        }
    ) == "next_queries"


def test_should_continue_insufficient_sources_next_queries() -> None:
    assert _should_continue(
        {
            "sources": [{"text": "a"}],
            "retrieval_round": 1,
            "use_web_search": True,
        }
    ) == "next_queries"


def test_should_continue_no_sources_without_web_reports() -> None:
    assert _should_continue(
        {
            "sources": [],
            "retrieval_round": 1,
            "use_web_search": False,
        }
    ) == "report"


def test_should_continue_max_rounds_force_report() -> None:
    assert _should_continue(
        {"sources": [], "retrieval_round": 3}
    ) == "report"
