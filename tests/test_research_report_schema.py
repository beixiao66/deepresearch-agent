import pytest
from pydantic import ValidationError

from app.schemas.research_report import ResearchReport, ResearchRequest


def test_research_request_strips_topic() -> None:
    request = ResearchRequest(
        topic="   Agentic RAG   ",
        knowledge_base_id=2,
    )
    assert request.topic == "Agentic RAG"
    assert request.knowledge_base_id == 2


@pytest.mark.parametrize("topic", ["", "   "])
def test_research_request_rejects_empty_topic(topic: str) -> None:
    with pytest.raises(ValidationError):
        ResearchRequest(topic=topic)


def test_research_request_default_knowledge_base() -> None:
    request = ResearchRequest(topic="RAG")
    assert request.knowledge_base_id == 1


def test_research_report_accepts_sources() -> None:
    from app.schemas.research import ResearchPlan
    from app.schemas.research_report import SourceItem

    plan = ResearchPlan(
        topic="RAG",
        objective="了解 RAG",
        sub_questions=["什么是 RAG？"],
        search_queries=["RAG 原理"],
    )
    report = ResearchReport(
        topic="RAG",
        plan=plan,
        sources=[
            SourceItem(
                document_id=1,
                chunk_index=3,
                text="RAG 是检索增强生成",
                score=0.85,
                query="RAG 原理",
            )
        ],
        answer="RAG 是检索增强生成。",
    )

    assert report.sources[0].score == 0.85
    assert report.answer == "RAG 是检索增强生成。"
