# tests/test_conversation_repository.py
import asyncio

import pytest
from sqlalchemy.exc import IntegrityError
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

    yield Session

    # 不 dispose 的话，连接池里的 aiosqlite 连接会在事件循环关闭后
    # 被 GC，__del__ 触发 "Exception ignored" unraisable 告警
    asyncio.run(engine.dispose())


def test_create_get_touch_and_list(session_factory) -> None:
    async def main() -> None:
        async with session_factory() as session:
            repository = ConversationRepository(session)
            await repository.create("conv-a", title="什么是 RAG？")
            await repository.create("conv-b", title="LangGraph 是？")
            await session.commit()

            conversation = await repository.get("conv-a")
            assert conversation is not None
            assert conversation.title == "什么是 RAG？"

            assert await repository.touch("conv-a") is True
            assert await repository.touch("conv-missing") is False
            await session.commit()

            listed = await repository.list_by_user()
            # updated_at 最近的在前面（conv-a 刚 touch）
            assert [item.id for item in listed] == ["conv-a", "conv-b"]

    asyncio.run(main())


def test_get_missing_returns_none(session_factory) -> None:
    async def main() -> None:
        async with session_factory() as session:
            repository = ConversationRepository(session)
            assert await repository.get("conv-not-exist") is None

    asyncio.run(main())


def test_create_duplicate_id_raises(session_factory) -> None:
    async def main() -> None:
        async with session_factory() as session:
            repository = ConversationRepository(session)
            await repository.create("conv-a", title="第一次")
            await session.commit()

            # flush 在 create 内部发生，重复主键在 create 时就抛
            with pytest.raises(IntegrityError):
                await repository.create("conv-a", title="重复")

    asyncio.run(main())
