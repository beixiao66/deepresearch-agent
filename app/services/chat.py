# app/services/chat.py
"""chat 业务编排：会话元数据 + 图调用 + 消息恢复。"""
import logging
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.conversation import ConversationRepository
from app.services.chat_graph import get_chat_graph

logger = logging.getLogger(__name__)


async def send_message(
        question: str,
        conversation_id: str | None,
        session: AsyncSession,
) -> tuple[str, str]:
    """发送一条消息。新会话（id 为空或不存在）生成新 conversation_id。"""
    repository = ConversationRepository(session)

    if conversation_id is None:
        conversation_id = uuid4().hex
        await repository.create(
            conversation_id,
            title=question[:100],
        )
    else:
        conversation = await repository.get(conversation_id)
        if conversation is None:
            conversation_id = uuid4().hex
            await repository.create(
                conversation_id,
                title=question[:100],
            )
        else:
            await repository.touch(conversation_id)

    await session.commit()

    graph = await get_chat_graph()
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=question)]},
        config={"configurable": {"thread_id": f"chat-{conversation_id}"}},
    )
    answer = str(result["messages"][-1].content)
    return answer, conversation_id


async def list_conversations(
        session: AsyncSession,
        user_id: int = 1,
) -> list[dict]:
    repository = ConversationRepository(session)
    return [
        {
            "id": item.id,
            "title": item.title,
            "updated_at": item.updated_at,
        }
        for item in await repository.list_by_user(user_id)
    ]


async def get_conversation_messages(
        conversation_id: str,
) -> list[dict]:
    graph = await get_chat_graph()
    snapshot = await graph.aget_state(
        {"configurable": {"thread_id": f"chat-{conversation_id}"}}
    )
    return [
        {
            "role": "assistant" if isinstance(message, AIMessage) else "user",
            "content": str(message.content),
        }
        for message in snapshot.values.get("messages", [])
        if isinstance(message, (HumanMessage, AIMessage))
    ]
