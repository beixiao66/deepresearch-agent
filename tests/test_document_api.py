from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from app.api.dependencies import get_document_service
from app.core.exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    KnowledgeBaseNotFoundError,
    UnsupportedDocumentTypeError,
    DocumentNotFoundError,
)
from app.main import app
from app.models.document import Document, DocumentStatus


def build_document() -> Document:
    timestamp = datetime.now(timezone.utc)

    return Document(
        id=1,
        knowledge_base_id=1,
        original_filename="rag.md",
        storage_path="data/uploads/1/uuid.md",
        file_extension=".md",
        file_size=1024,
        mime_type="text/markdown",
        status=DocumentStatus.PENDING.value,
        created_at=timestamp,
        updated_at=timestamp,
    )


def create_client_with_service(service: Mock) -> TestClient:
    app.dependency_overrides[
        get_document_service
    ] = lambda: service

    return TestClient(app)


def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()


def build_upload(
        filename: str,
        content: bytes,
):
    return {
        "file": (
            filename,
            BytesIO(content),
            "application/octet-stream",
        )
    }


def test_upload_document_returns_201() -> None:
    service = Mock()
    service.upload_document = AsyncMock(
        return_value=build_document()
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases/1/documents",
            files=build_upload("rag.md", b"content"),
        )

        assert response.status_code == 201
        assert response.json()["original_filename"] == "rag.md"
        assert response.json()["status"] == "pending"
        service.upload_document.assert_awaited_once()
    finally:
        clear_dependency_overrides()


def test_upload_document_returns_404() -> None:
    service = Mock()
    service.upload_document = AsyncMock(
        side_effect=KnowledgeBaseNotFoundError(999)
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases/999/documents",
            files=build_upload("rag.md", b"content"),
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == (
            "KNOWLEDGE_BASE_NOT_FOUND"
        )
    finally:
        clear_dependency_overrides()


def test_upload_document_returns_415() -> None:
    service = Mock()
    service.upload_document = AsyncMock(
        side_effect=UnsupportedDocumentTypeError(".exe")
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases/1/documents",
            files=build_upload("malware.exe", b"content"),
        )

        assert response.status_code == 415
        assert response.json()["error"]["code"] == (
            "UNSUPPORTED_DOCUMENT_TYPE"
        )
    finally:
        clear_dependency_overrides()


def test_upload_document_returns_413() -> None:
    service = Mock()
    service.upload_document = AsyncMock(
        side_effect=DocumentTooLargeError(10)
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases/1/documents",
            files=build_upload("large.md", b"content"),
        )

        assert response.status_code == 413
        assert response.json()["error"]["code"] == (
            "DOCUMENT_TOO_LARGE"
        )
    finally:
        clear_dependency_overrides()


def test_upload_document_returns_400() -> None:
    service = Mock()
    service.upload_document = AsyncMock(
        side_effect=EmptyDocumentError()
    )
    client = create_client_with_service(service)

    try:
        response = client.post(
            "/api/v1/knowledge-bases/1/documents",
            files=build_upload("empty.txt", b""),
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == (
            "EMPTY_DOCUMENT"
        )
    finally:
        clear_dependency_overrides()


def test_list_documents_returns_200() -> None:
    service = Mock()
    service.list_by_knowledge_base = AsyncMock(
        return_value=[build_document()]
    )
    client = create_client_with_service(service)

    try:
        response = client.get(
            "/api/v1/knowledge-bases/1/documents"
        )

        assert response.status_code == 200
        assert response.json()[0]["id"] == 1
        service.list_by_knowledge_base.assert_awaited_once_with(
            1
        )
    finally:
        clear_dependency_overrides()


def test_delete_document_returns_204() -> None:
    service = Mock()
    service.delete_document = AsyncMock()
    client = create_client_with_service(service)

    try:
        response = client.delete(
            "/api/v1/knowledge-bases/1/documents/1"
        )

        assert response.status_code == 204
        service.delete_document.assert_awaited_once_with(
            knowledge_base_id=1,
            document_id=1,
        )
    finally:
        clear_dependency_overrides()


def test_delete_document_returns_404() -> None:
    service = Mock()
    service.delete_document = AsyncMock(
        side_effect=DocumentNotFoundError(999)
    )
    client = create_client_with_service(service)

    try:
        response = client.delete(
            "/api/v1/knowledge-bases/1/documents/999"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == (
            "DOCUMENT_NOT_FOUND"
        )
    finally:
        clear_dependency_overrides()