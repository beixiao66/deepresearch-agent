from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.chat import ChatResponse, ChatRequest
from app.services.llm import get_llm

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("",response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    response = await get_llm().ainvoke(request.question)
    settings = get_settings()
    return ChatResponse(
        answer=response.content,
        model=settings.llm_model,
    )