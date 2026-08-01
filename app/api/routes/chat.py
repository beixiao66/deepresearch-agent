from fastapi import APIRouter, HTTPException, status
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import get_settings
from app.schemas.chat import ChatResponse, ChatRequest
from app.services.llm import get_llm
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("",response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        messages = [
            SystemMessage(
                content=(
                    "你是一名 AI 技术研究助手。"
                    "请准确、简洁地回答用户问题；"
                    "不确定时应明确说明，不要编造信息。"
                )
            ),
            HumanMessage(content=request.question)
        ]
        response = await get_llm().ainvoke(messages)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Model service authentication failed"
        ) from e
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model service is temporarily busy",
        ) from exc
    except APITimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Model service timed out",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to model service",
        ) from exc
    except APIStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Model service returned an error",
        ) from exc
    settings = get_settings()
    return ChatResponse(
        answer=str(response.content),
        model=settings.llm_model,
    )