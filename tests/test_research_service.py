import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.research import ResearchPlan
from app.schemas.research_report import ResearchReport, ResearchRequest
from app.services.research import get_research_graph, run_research
from app.services.research_graph import build_research_graph


def test_build_research_graph_has_expected_structure() -> None:
    graph = build_research_graph()

    nodes = graph.get_graph().nodes
    edges = graph.get_graph().edges

    assert "plan" in nodes
    assert "retrieve" in nodes
    assert "report" in nodes
    assert "__start__" in nodes
    assert "__end__" in nodes

    plain_edges = [
        (edge.source, edge.target)
        for edge in edges
        if not edge.conditional
    ]
    assert ("__start__", "plan") in plain_edges
    assert ("plan", "retrieve") in plain_edges
    assert ("retrieve", "report") in plain_edges
    assert ("report", "__end__") in plain_edges


def test_run_research_returns_report(monkeypatch) -> None:
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

    request = ResearchRequest(
        topic="Agentic RAG",
        knowledge_base_id=1,
    )
    report = asyncio.run(run_research(request))

    assert isinstance(report, ResearchReport)
    assert report.topic == "Agentic RAG"
    assert report.plan == plan
    assert len(report.sources) == 1
    assert report.sources[0].text == "Agentic RAG 是……"
    assert report.answer == "Agentic RAG 是……"
    fake_graph.ainvoke.assert_awaited_once()
