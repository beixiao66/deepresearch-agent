from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from app.api.dependencies import get_knowledge_base_service
from app.core.exceptions import (
      KnowledgeBaseNameConflictError,
      KnowledgeBaseNotFoundError,
)
from app.main import app
from app.models.knowledge_base import KnowledgeBase


def build_knowledge_base(
        knowledge_base_id: int = 1,
        name: str = "AI 技术资料库",
) -> KnowledgeBase:
    timestamp = datetime.now(timezone.utc)

    return KnowledgeBase(
        id=knowledge_base_id,
        name=name,
        description="RAG 与 Agent 相关资料",
        created_at=timestamp,
        updated_at=timestamp,
    )


def create_client_with_service(
        service: Mock,
) -> TestClient:
    app.dependency_overrides[
        get_knowledge_base_service
    ] = lambda: service

    return TestClient(app)


def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()


def test_create_knowledge_base_returns_201() -> None:
    service = Mock()
    service.create = AsyncMock(
        return_value=build_knowledge_base()
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases",
            json={
                "name": "   AI 技术资料库   ",
                "description": "RAG 与 Agent 相关资料",
            },
        )

        assert response.status_code == 201
        assert response.json()["name"] == "AI 技术资料库"
        service.create.assert_awaited_once()
        create_data = service.create.await_args.args[0]
        assert create_data.name == "AI 技术资料库"
    finally:
        clear_dependency_overrides()


def test_list_knowledge_bases_returns_200() -> None:
    service = Mock()
    service.list_all = AsyncMock(
        return_value=[
            build_knowledge_base(
                knowledge_base_id=2,
                name="Agent 资料库",
            ),
            build_knowledge_base(
                knowledge_base_id=1,
                name="RAG 资料库",
            ),
        ]
    )
    client = create_client_with_service(service)

    try:
        response = client.get(
            "/api/v1/knowledge-bases"
        )

        assert response.status_code == 200
        assert [
                   item["id"] for item in response.json()
               ] == [2, 1]
        service.list_all.assert_awaited_once()
    finally:
        clear_dependency_overrides()


def test_get_knowledge_base_returns_404() -> None:
    service = Mock()
    service.get_by_id = AsyncMock(
        side_effect=KnowledgeBaseNotFoundError(999)
    )
    client = create_client_with_service(service)

    try:
        response = client.get(
            "/api/v1/knowledge-bases/999"
        )

        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "code": "KNOWLEDGE_BASE_NOT_FOUND",
                "message": "Knowledge base not found",
            }
        }
        service.get_by_id.assert_awaited_once_with(999)
    finally:
        clear_dependency_overrides()


def test_create_knowledge_base_returns_409() -> None:
    service = Mock()
    service.create = AsyncMock(
        side_effect=KnowledgeBaseNameConflictError(
            "AI 技术资料库"
        )
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "AI 技术资料库"},
        )

        assert response.status_code == 409
        assert response.json() == {
            "error": {
                "code": "KNOWLEDGE_BASE_NAME_CONFLICT",
                "message": "Knowledge base name already exists",
            }
        }
    finally:
        clear_dependency_overrides()