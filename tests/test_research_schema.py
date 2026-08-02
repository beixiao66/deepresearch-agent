import pytest
from pydantic import ValidationError

from app.schemas.research import ResearchPlan, ResearchPlanRequest


def test_research_plan_request_strips_topic() -> None:
    request = ResearchPlanRequest(topic="   RAG 企业知识库   ")
    assert request.topic == "RAG 企业知识库"


@pytest.mark.parametrize("topic", ["", "   "])
def test_research_plan_request_rejects_empty_topic(topic: str) -> None:
    with pytest.raises(ValidationError):
        ResearchPlanRequest(topic=topic)


def test_research_plan_normalizes_generated_text() -> None:
    plan = ResearchPlan(
        topic="  RAG  ",
        objective="  了解 RAG  ",
        sub_questions=["  什么是 RAG？  ", "   "],
        search_queries=["  RAG 原理  "],
    )

    assert plan.model_dump() == {
        "topic": "RAG",
        "objective": "了解 RAG",
        "sub_questions": ["什么是 RAG？"],
        "search_queries": ["RAG 原理"],
    }


def test_research_plan_rejects_lists_with_only_blank_items() -> None:
    with pytest.raises(ValidationError):
        ResearchPlan(
            topic="RAG",
            objective="了解 RAG",
            sub_questions=["   "],
            search_queries=["RAG 原理"],
        )