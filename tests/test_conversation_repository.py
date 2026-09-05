# tests/test_conversation_repository.py
import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import conversation  # noqa: F401 确保模型注册进 metadata
from app.repositories.conversation import ConversationRepository


@pytest.fixture
def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/conv.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def main() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(main())

    return Session


def test_create_get_touch_and_list(session_factory) -> None:
    async def main() -> None:
        async with session_factory() as session:
            repository = ConversationRepository(session)
            await repository.create("id-a", title="什么是 RAG？")
            await repository.create("id-b", title="LangGraph 是？")
            await session.commit()

            conversation = await repository.get("id-a")
            assert conversation is not None
            assert conversation.title == "什么是 RAG？"

            await repository.touch("id-a")
            await session.commit()

            listed = await repository.list_by_user()
            # updated_at 最近的在前面（id-a 刚 touch）
            assert [item.id for item in listed] == ["id-a", "id-b"]

    asyncio.run(main())
