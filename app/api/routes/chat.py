from fastapi import APIRouter
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import get_settings
from app.schemas.chat import ChatResponse, ChatRequest
from app.services.llm import get_llm


router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("",response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
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
    settings = get_settings()
    return ChatResponse(
        answer=str(response.content),
        model=settings.llm_model,
    )