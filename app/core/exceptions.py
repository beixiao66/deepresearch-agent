import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
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
            f"知识库不存在: {knowledge_base_id}"
        )


class KnowledgeBaseNameConflictError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"知识库名称已存在: {name}"
        )


class UnsupportedDocumentTypeError(Exception):
    def __init__(self, file_extension: str) -> None:
        self.file_extension = file_extension
        super().__init__(
            f"Unsupported document type: {file_extension}"
        )


class EmptyDocumentError(Exception):
    pass


class DocumentTooLargeError(Exception):
    def __init__(
            self,
            max_file_size: int,
    ) -> None:
        self.max_file_size = max_file_size
        super().__init__(
            f"Document exceeds maximum size: {max_file_size}"
        )


class DocumentNotFoundError(Exception):
    def __init__(self, document_id: int) -> None:
        self.document_id = document_id
        super().__init__(
            f"文档不存在: {document_id}"
        )


class ResearchTaskNotFoundError(Exception):
    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(f"Research task not found: {task_id}")


class ResearchTaskInvalidStateError(Exception):
    def __init__(self, task_id: int, status: str) -> None:
        self.task_id = task_id
        self.status = status
        super().__init__(
            f"Research task is not awaiting approval: {task_id}, {status}"
        )


MODEL_ERROR_MAPPINGS: list[tuple[type[Exception], ErrorMapping]] = [
    (
        AuthenticationError,
        ErrorMapping(
            status_code=502,
            code="MODEL_AUTHENTICATION_FAILED",
            message="模型服务认证失败，请联系管理员检查配置",
        ),
    ),
    (
        RateLimitError,
        ErrorMapping(
            status_code=503,
            code="MODEL_RATE_LIMITED",
            message="模型服务当前繁忙，请稍后重试",
        ),
    ),
    (
        APITimeoutError,
        ErrorMapping(
            status_code=504,
            code="MODEL_TIMEOUT",
            message="模型服务响应超时，请稍后重试",
        ),
    ),
    (
        APIConnectionError,
        ErrorMapping(
            status_code=503,
            code="MODEL_CONNECTION_FAILED",
            message="暂时无法连接模型服务，请稍后重试",
        ),
    ),
    (
        APIStatusError,
        ErrorMapping(
            status_code=502,
            code="MODEL_SERVICE_ERROR",
            message="模型服务处理失败，请稍后重试",
        ),
    ),
]


def get_public_error(exc: Exception) -> ErrorMapping:
    for error_type, mapping in MODEL_ERROR_MAPPINGS:
        if isinstance(exc, error_type):
            return mapping
    if isinstance(exc, ResearchTaskNotFoundError):
        return ErrorMapping(404, "RESEARCH_TASK_NOT_FOUND", "研究任务不存在")
    if isinstance(exc, ResearchTaskInvalidStateError):
        return ErrorMapping(
            409,
            "RESEARCH_TASK_INVALID_STATE",
            "当前任务状态不允许执行此操作",
        )
    return ErrorMapping(
        500,
        "INTERNAL_SERVER_ERROR",
        "服务器处理失败，请稍后重试",
    )


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

    app.add_exception_handler(
        UnsupportedDocumentTypeError,
        handle_unsupported_document_type,
    )
    app.add_exception_handler(
        EmptyDocumentError,
        handle_empty_document,
    )
    app.add_exception_handler(
        DocumentTooLargeError,
        handle_document_too_large,
    )

    app.add_exception_handler(
        DocumentNotFoundError,
        handle_document_not_found,
    )
    app.add_exception_handler(
        ResearchTaskNotFoundError,
        handle_research_task_not_found,
    )
    app.add_exception_handler(
        ResearchTaskInvalidStateError,
        handle_research_task_invalid_state,
    )
    app.add_exception_handler(
        RequestValidationError,
        handle_request_validation_error,
    )
    app.add_exception_handler(
        StarletteHTTPException,
        handle_http_exception,
    )


async def handle_knowledge_base_not_found(
        request: Request,
        exc: KnowledgeBaseNotFoundError,
) -> JSONResponse:
    logger.info(
        "知识库不存在: id=%d, path=%s",
        exc.knowledge_base_id,
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="KNOWLEDGE_BASE_NOT_FOUND",
            message="知识库不存在",
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
            message="知识库名称已存在",
        )
    )

    return JSONResponse(
        status_code=409,
        content=error_response.model_dump(),
    )


async def handle_unsupported_document_type(
        request: Request,
        exc: UnsupportedDocumentTypeError,
) -> JSONResponse:
    logger.info(
        "Unsupported document type: extension=%s, path=%s",
        exc.file_extension,
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="UNSUPPORTED_DOCUMENT_TYPE",
            message="仅支持 PDF、Markdown 和 TXT 文件",
        )
    )

    return JSONResponse(
        status_code=415,
        content=error_response.model_dump(),
    )


async def handle_empty_document(
        request: Request,
        _exc: EmptyDocumentError,
) -> JSONResponse:
    logger.info(
        "Empty document rejected: path=%s",
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="EMPTY_DOCUMENT",
            message="上传的文档不能为空",
        )
    )

    return JSONResponse(
        status_code=400,
        content=error_response.model_dump(),
    )


async def handle_document_too_large(
        request: Request,
        exc: DocumentTooLargeError,
) -> JSONResponse:
    logger.info(
        "Document too large: max_size=%d, path=%s",
        exc.max_file_size,
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="DOCUMENT_TOO_LARGE",
            message="上传的文档超过大小限制",
        )
    )

    return JSONResponse(
        status_code=413,
        content=error_response.model_dump(),
    )


async def handle_research_task_not_found(
        request: Request,
        exc: ResearchTaskNotFoundError,
) -> JSONResponse:
    logger.info(
        "Research task not found: id=%d, path=%s",
        exc.task_id,
        request.url.path,
    )
    return _error_response(
        404,
        "RESEARCH_TASK_NOT_FOUND",
        "研究任务不存在",
    )


async def handle_research_task_invalid_state(
        request: Request,
        exc: ResearchTaskInvalidStateError,
) -> JSONResponse:
    logger.info(
        "Research task invalid state: id=%d, status=%s, path=%s",
        exc.task_id,
        exc.status,
        request.url.path,
    )
    return _error_response(
        409,
        "RESEARCH_TASK_INVALID_STATE",
        "当前任务状态不允许执行此操作",
    )


async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
) -> JSONResponse:
    logger.info(
        "Request validation failed: path=%s, errors=%s",
        request.url.path,
        exc.errors(),
    )
    return _error_response(
        422,
        "REQUEST_VALIDATION_FAILED",
        "请求参数不正确，请检查后重试",
    )


async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
) -> JSONResponse:
    messages = {
        404: "请求的资源不存在",
        405: "不支持该请求方式",
    }
    return _error_response(
        exc.status_code,
        "HTTP_ERROR",
        messages.get(exc.status_code, "请求处理失败"),
    )


def _error_response(
        status_code: int,
        code: str,
        message: str,
) -> JSONResponse:
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(),
    )


async def handle_document_not_found(
        request: Request,
        exc: DocumentNotFoundError,
) -> JSONResponse:
    logger.info(
        "文档不存在: id=%d, path=%s",
        exc.document_id,
        request.url.path,
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="DOCUMENT_NOT_FOUND",
            message="文档不存在",
        )
    )

    return JSONResponse(
        status_code=404,
        content=error_response.model_dump(),
    )