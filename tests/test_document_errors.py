from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
    register_exception_handlers,
)

app_under_test = FastAPI()
register_exception_handlers(app_under_test)


@app_under_test.get("/unsupported")
async def raise_unsupported_type() -> None:
    raise UnsupportedDocumentTypeError(".exe")


@app_under_test.get("/empty")
async def raise_empty_document() -> None:
    raise EmptyDocumentError()


@app_under_test.get("/too-large")
async def raise_document_too_large() -> None:
    raise DocumentTooLargeError(10 * 1024 * 1024)


client = TestClient(app_under_test)


def test_unsupported_document_type_returns_415() -> None:
    response = client.get("/unsupported")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == (
        "UNSUPPORTED_DOCUMENT_TYPE"
    )


def test_empty_document_returns_400() -> None:
    response = client.get("/empty")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_DOCUMENT"


def test_document_too_large_returns_413() -> None:
    response = client.get("/too-large")

    assert response.status_code == 413
    assert response.json()["error"]["code"] == (
          "DOCUMENT_TOO_LARGE"
    )