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
    _fanout,
    _report,
    _researcher,
    build_research_graph,
)
from langgraph.types import Send


def build_plan() -> ResearchPlan:
    return ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=[
            "Agentic RAG 是什么？",
            "Agentic RAG 有哪些应用？",
        ],
        search_queries=["Agentic RAG"],
    )


def test_build_research_graph_has_expected_structure() -> None:
    graph = build_research_graph()

    nodes = graph.get_graph().nodes
    edges = graph.get_graph().edges

    assert "plan" in nodes
    assert "review" in nodes
    assert "dispatch" in nodes
    assert "researcher" in nodes
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
    assert ("review", "dispatch") in plain_edges
    assert ("researcher", "report") in plain_edges
    assert ("report", "__end__") in plain_edges

    # dispatch 通过条件边（Send 并行分发）到 researcher
    conditional_edges = [
        (edge.source, edge.target)
        for edge in edges
        if edge.conditional
    ]
    assert ("dispatch", "researcher") in conditional_edges


def test_fanout_returns_send_for_each_sub_question() -> None:
    plan = build_plan()
    sends = _fanout(
        {
            "question": "Agentic RAG",
            "knowledge_base_id": 1,
            "use_web_search": False,
            "plan": plan,
        }
    )

    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)
    assert sends[0].node == "researcher"
    assert sends[0].arg["question"] == "Agentic RAG 是什么？"
    assert sends[1].arg["question"] == "Agentic RAG 有哪些应用？"
    assert sends[0].arg["knowledge_base_id"] == 1


def test_start_research_pauses_at_plan_review(
        monkeypatch,
) -> None:
    plan = build_plan()

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
    plan = build_plan()

    fake_graph = Mock()
    fake_graph.ainvoke = AsyncMock(
        return_value={
            "plan": plan,
            "sub_answers": [
                {
                    "question": "Agentic RAG 是什么？",
                    "answer": "Agentic RAG 是……",
                    "sources": [
                        {
                            "document_id": 1,
                            "chunk_index": 2,
                            "text": "Agentic RAG 是……",
                            "score": 0.9,
                            "query": "Agentic RAG",
                        }
                    ],
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
    assert report.sources[0].document_id == 1
    assert report.answer == "Agentic RAG 是……"
    fake_graph.ainvoke.assert_awaited_once()


def test_approve_research_cancelled_marks_cancelled(
        monkeypatch,
) -> None:
    plan = build_plan()

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
        plan=plan.model_dump_json(),
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
    status_call = task_repository.update_status.await_args_list[-1]
    assert status_call.args[1] == ResearchTaskStatus.CANCELLED
    assert status_call.kwargs["error_message"] == "用户已取消此次研究任务"


def test_report_without_sub_answers_does_not_call_llm(
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
            "sub_answers": [],
        })
    )

    assert "暂无足够资料" in result["answer"]
    mock_llm.ainvoke.assert_not_awaited()


def test_researcher_without_evidence_returns_placeholder(
        monkeypatch,
) -> None:
    """子 Agent 无证据时返回占位回答，不调用 LLM。"""
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock()
    monkeypatch.setattr(
        "app.services.research_graph.get_llm",
        lambda: mock_llm,
    )

    plan = build_plan()
    result = asyncio.run(
        _researcher({
            "question": "Agentic RAG 是什么？",
            "knowledge_base_id": 999,
            "use_web_search": False,
            "plan": plan,
        })
    )

    assert len(result["sub_answers"]) == 1
    sub_answer = result["sub_answers"][0]
    assert "暂无足够资料" in sub_answer["answer"]
    # 无证据时不调用 LLM（子 Agent 内部没有生成回答）
    mock_llm.ainvoke.assert_not_awaited()
