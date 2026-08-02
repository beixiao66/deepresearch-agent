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