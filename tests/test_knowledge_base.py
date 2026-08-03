import pytest
from pydantic import ValidationError

from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
)


def test_knowledge_base_create_strips_input() -> None:
    data = KnowledgeBaseCreate(
        name="   AI 技术资料库   ",
        description="   RAG 与 Agent 资料   ",
    )

    assert data.name == "AI 技术资料库"
    assert data.description == "RAG 与 Agent 资料"


@pytest.mark.parametrize("name", ["", "   "])
def test_knowledge_base_create_rejects_blank_name(
        name: str,
) -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(name=name)


def test_knowledge_base_create_converts_blank_description_to_none() -> None:
    data = KnowledgeBaseCreate(
        name="AI 技术资料库",
        description="   ",
    )

    assert data.description is None