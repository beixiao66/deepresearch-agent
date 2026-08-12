import asyncio
from unittest.mock import AsyncMock

import pytest
import httpx

from fastapi.testclient import TestClient

from openai import AuthenticationError

from app.api.dependencies import (
    get_document_service,
    get_knowledge_base_service,
)
from app.main import app
from app.schemas.research import ResearchPlan
from app.schemas.research_report import ResearchReport, ResearchRequest

client = TestClient(app)


@pytest.mark.parametrize("topic", ["", "   "])
def test_research_rejects_empty_topic(topic: str) -> None:
    response = client.post(
        "/api/v1/research",
        data={"topic": topic, "knowledge_base_id": "1"},
    )
    assert response.status_code == 422


def test_research_returns_mocked_report(monkeypatch) -> None:
    async def fake_stream(
            request,
            task_repository,
            knowledge_base_service=None,
            temp_kb_prefix=None,
    ):
        yield "data: {\"type\": \"task_created\", \"task_id\": 1}\n\n"
        yield "data: {\"type\": \"awaiting_approval\"}\n\n"

    monkeypatch.setattr(
        "app.api.routes.research.stream_start_research",
        fake_stream,
    )

    response = client.post(
        "/api/v1/research",
        data={"topic": "   Agentic RAG   ", "knowledge_base_id": "1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )
    assert "task_created" in response.text
    assert "awaiting_approval" in response.text


def test_research_requires_knowledge_base_or_file() -> None:
    response = client.post(
        "/api/v1/research",
        data={"topic": "Agentic RAG"},
    )
    assert response.status_code == 422


def test_research_with_file_creates_temp_kb(monkeypatch) -> None:
    """上传文件创建研究：自动建临时知识库并索引，再用该库研究。"""
    captured = {}

    async def fake_stream(
            request,
            task_repository,
            knowledge_base_service=None,
            temp_kb_prefix=None,
    ):
        captured["request"] = request
        captured["temp_kb_prefix"] = temp_kb_prefix
        yield "data: {\"type\": \"task_created\", \"task_id\": 1}\n\n"
        yield "data: {\"type\": \"awaiting_approval\"}\n\n"

    monkeypatch.setattr(
        "app.api.routes.research.stream_start_research",
        fake_stream,
    )

    # mock 临时知识库服务与文档服务（依赖注入覆盖）
    class FakeKB:
        id = 99
        name = "研究附件-abc123"

    mock_kb_service = AsyncMock()
    mock_kb_service.create = AsyncMock(return_value=FakeKB())

    mock_doc_service = AsyncMock()
    mock_doc_service.upload_document = AsyncMock()

    app.dependency_overrides[get_knowledge_base_service] = (
        lambda: mock_kb_service
    )
    app.dependency_overrides[get_document_service] = (
        lambda: mock_doc_service
    )

    try:
        response = client.post(
            "/api/v1/research",
            data={"topic": "分析这份简历", "knowledge_base_id": ""},
            files={"file": ("resume.txt", b"test resume content", "text/plain")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["request"].knowledge_base_id == 99
    mock_kb_service.create.assert_awaited_once()
    mock_doc_service.upload_document.assert_awaited_once()
    assert "task_created" in response.text
