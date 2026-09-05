# tests/test_chat_service.py
import asyncio
from unittest.mock import AsyncMock, Mock

import aiosqlite
import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from openai import RateLimitError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import conversation  # noqa: F401
from app.services import chat


@pytest.fixture(autouse=True)
def reset_chat_graph():
    """chat_graph._chat_graph 是进程级单例，缓存了上个测试已关闭的
    checkpointer 连接；每测重置，build_chat_graph 才会用本测试的 mock。"""
    import app.services.chat_graph as chat_graph_module

    chat_graph_module._chat_graph = None
    yield
    chat_graph_module._chat_graph = None


@pytest.fixture
def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/conv.db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def main() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(main())

    yield Session

    asyncio.run(engine.dispose())


def _build_test_graph(tmp_path, monkeypatch, answers):
    """真实 chat 图 + 临时 checkpointer + mock LLM。"""
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[AIMessage(content=answer) for answer in answers]
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )

    # aiosqlite 0.22+ 的 connect() 直接返回 Connection（可 await，但不是
    # coroutine），且 AsyncSqliteSaver 构造要求运行中的事件循环，
    # 因此连接、构造 saver、setup 在同一个 asyncio.run 内完成。
    async def open_connection() -> AsyncSqliteSaver:
        conn = await aiosqlite.connect(str(tmp_path / "checkpoints.db"))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        return saver

    saver = asyncio.run(open_connection())
    conn = saver.conn
    monkeypatch.setattr(
        "app.services.chat_graph.get_checkpointer",
        AsyncMock(return_value=saver),
    )
    return mock_llm, conn


def test_send_message_new_conversation_returns_id(
        session_factory, tmp_path, monkeypatch,
) -> None:
    _, conn = _build_test_graph(tmp_path, monkeypatch, ["回答一"])

    async def main() -> None:
        async with session_factory() as session:
            answer, conversation_id = await chat.send_message(
                "什么是 RAG？", None, session
            )
            assert answer == "回答一"
            assert len(conversation_id) == 32

            conversations = await chat.list_conversations(session)
            assert conversations[0]["id"] == conversation_id
            assert conversations[0]["title"] == "什么是 RAG？"

    asyncio.run(main())
    asyncio.run(conn.close())


def test_retry_after_failure_does_not_duplicate_question(
        session_factory, tmp_path, monkeypatch,
) -> None:
    """上轮生成失败（以用户消息结尾）后重试，历史里问题只出现一次。"""
    request = httpx.Request("POST", "https://model.example.com/chat")
    rate_error = RateLimitError(
        "Rate limit exceeded",
        response=httpx.Response(status_code=429, request=request),
        body=None,
    )

    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[rate_error, AIMessage(content="第二次回答")]
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )

    async def open_connection() -> AsyncSqliteSaver:
        conn = await aiosqlite.connect(str(tmp_path / "checkpoints.db"))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        return saver

    saver = asyncio.run(open_connection())
    conn = saver.conn
    monkeypatch.setattr(
        "app.services.chat_graph.get_checkpointer",
        AsyncMock(return_value=saver),
    )

    async def main() -> None:
        async with session_factory() as session:
            with pytest.raises(RateLimitError):
                await chat.send_message("重试问题", None, session)

            # 失败时会话记录已提交，重试用同一 id
            conversations = await chat.list_conversations(session)
            conversation_id = conversations[0]["id"]

            answer, returned_id = await chat.send_message(
                "重试问题", conversation_id, session
            )
            assert answer == "第二次回答"
            assert returned_id == conversation_id

            messages = await chat.get_conversation_messages(conversation_id)
            assert messages == [
                {"role": "user", "content": "重试问题"},
                {"role": "assistant", "content": "第二次回答"},
            ]

    asyncio.run(main())
    asyncio.run(conn.close())


def test_send_message_same_conversation_keeps_history(
        session_factory, tmp_path, monkeypatch,
) -> None:
    mock_llm, conn = _build_test_graph(
        tmp_path, monkeypatch, ["答1", "答2"]
    )

    async def main() -> None:
        async with session_factory() as session:
            _, conversation_id = await chat.send_message(
                "第一问", None, session
            )
            await chat.send_message(
                "第二问", conversation_id, session
            )
            sent = mock_llm.ainvoke.await_args.args[0]
            contents = [m.content for m in sent]
            assert "第一问" in contents
            assert "答1" in contents
            assert contents[-1] == "第二问"

    asyncio.run(main())
    asyncio.run(conn.close())


def test_get_conversation_messages_restores_history(
        session_factory, tmp_path, monkeypatch,
) -> None:
    _, conn = _build_test_graph(tmp_path, monkeypatch, ["答1"])

    async def main() -> None:
        async with session_factory() as session:
            _, conversation_id = await chat.send_message(
                "第一问", None, session
            )
            messages = await chat.get_conversation_messages(
                conversation_id
            )
            assert messages == [
                {"role": "user", "content": "第一问"},
                {"role": "assistant", "content": "答1"},
            ]

    asyncio.run(main())
    asyncio.run(conn.close())
