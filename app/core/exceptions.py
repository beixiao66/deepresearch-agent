import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ErrorMapping:
    status_code: int
    code: str
    message: str


class KnowledgeBaseNotFoundError(Exception):
    def __init__(self, knowledge_base_id: int) -> None:
        self.knowledge_base_id = knowledge_base_id
        super().__init__(
            f"Knowledge base not found: {knowledge_base_id}"
        )


class KnowledgeBaseNameConflictError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Knowledge base name already exists: {name}"
        )


MODEL_ERROR_MAPPINGS: list[tuple[type[Exception], ErrorMapping]] = [
    (
        AuthenticationError,
        ErrorMapping(
            status_code=502,
            code="MODEL_AUTHENTICATION_FAILED",
            message="Model service authentication failed",
        ),
    ),
    (
        RateLimitError,
        ErrorMapping(
            status_code=503,
            code="MODEL_RATE_LIMITED",
            message="Model service is temporarily busy",
        ),
    ),
    (
        APITimeoutError,
        ErrorMapping(
            status_code=504,
            code="MODEL_TIMEOUT",
            message="Model service timed out",
        ),
    ),
    (
        APIConnectionError,
        ErrorMapping(
            status_code=503,
            code="MODEL_CONNECTION_FAILED",
            message="Unable to connect to model service",
        ),
    ),
    (
        APIStatusError,
        ErrorMapping(
            status_code=502,
            code="MODEL_SERVICE_ERROR",
            message="Model service returned an error",
        ),
    ),
]


def get_error_mapping(exc: Exception) -> ErrorMapping:
    for error_type, mapping in MODEL_ERROR_MAPPINGS:
        if isinstance(exc, error_type):
            return mapping

    raise TypeError(
        f"Unsupported model error type: {type(exc).__name__}"
    )


async def handle_model_service_error(
        request: Request,
        exc: Exception,
) -> JSONResponse:
    mapping = get_error_mapping(exc)

    logger.error(
        "Model service error: type=%s, path=%s",
        type(exc).__name__,
        request.url.path,
        exc_info=True,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code=mapping.code,
            message=mapping.message,
        )
    )

    return JSONResponse(
        status_code=mapping.status_code,
        content=error_response.model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    for error_type, _mapping in MODEL_ERROR_MAPPINGS:
        app.add_exception_handler(
            error_type,
            handle_model_service_error,
        )

    app.add_exception_handler(
        KnowledgeBaseNotFoundError,
        handle_knowledge_base_not_found,
    )
    app.add_exception_handler(
        KnowledgeBaseNameConflictError,
        handle_knowledge_base_name_conflict,
    )


async def handle_knowledge_base_not_found(
        request: Request,
        exc: KnowledgeBaseNotFoundError,
) -> JSONResponse:
    logger.info(
        "Knowledge base not found: id=%d, path=%s",
        exc.knowledge_base_id,
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="KNOWLEDGE_BASE_NOT_FOUND",
            message="Knowledge base not found",
        )
    )

    return JSONResponse(
        status_code=404,
        content=error_response.model_dump(),
    )


async def handle_knowledge_base_name_conflict(
        request: Request,
        exc: KnowledgeBaseNameConflictError,
) -> JSONResponse:
    logger.warning(
        "Knowledge base name conflict: path=%s",
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="KNOWLEDGE_BASE_NAME_CONFLICT",
            message="Knowledge base name already exists",
        )
    )

    return JSONResponse(
        status_code=409,
        content=error_response.model_dump(),
    )