from fastapi import APIRouter, Response

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationMessages,
    ConversationSummary,
)
from app.services.chat import (
    delete_conversation,
    get_conversation_messages,
    list_conversations,
    send_message,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
        request: ChatRequest,
        session: DatabaseSession,
) -> ChatResponse:
    answer, conversation_id = await send_message(
        request.question,
        request.conversation_id,
        session,
    )
    return ChatResponse(
        answer=answer,
        model=get_settings().llm_model,
        conversation_id=conversation_id,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_chat_conversations(
        session: DatabaseSession,
) -> list[ConversationSummary]:
    return [
        ConversationSummary(**item)
        for item in await list_conversations(session)
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessages,
)
async def read_conversation_messages(
        conversation_id: str,
) -> ConversationMessages:
    messages = await get_conversation_messages(conversation_id)
    return ConversationMessages(
        conversation_id=conversation_id,
        messages=messages,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_chat_conversation(
        conversation_id: str,
        session: DatabaseSession,
) -> Response:
    """删除会话及其对话历史（checkpoint 线程）。"""
    await delete_conversation(conversation_id, session)
    return Response(status_code=204)
