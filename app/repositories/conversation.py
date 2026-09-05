# app/repositories/conversation.py
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
            self,
            conversation_id: str,
            title: str,
            user_id: int = 1,
    ) -> Conversation:
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id,
            title=title,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def get(
            self,
            conversation_id: str,
    ) -> Conversation | None:
        return await self.session.get(
            Conversation,
            conversation_id,
        )

    async def touch(self, conversation_id: str) -> bool:
        conversation = await self.get(conversation_id)
        if conversation is not None:
            conversation.updated_at = datetime.now(timezone.utc)
        return conversation is not None

    async def list_by_user(
            self,
            user_id: int = 1,
    ) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(
                Conversation.updated_at.desc(),
                Conversation.created_at.desc(),
            )
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
