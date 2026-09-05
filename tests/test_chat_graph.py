# tests/test_chat_graph.py
import asyncio
from unittest.mock import AsyncMock, Mock

import aiosqlite
import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.services.chat_graph import (
    _chat_node,
    _summarize_node,
    build_chat_graph,
)
from app.services.llm import CHAT_SYSTEM_PROMPT


@pytest.fixture
def temp_checkpointer(tmp_path):
    """临时文件 checkpointer，测试结束关闭连接（避免 aiosqlite 线程挂起）。"""
    savers = []

    async def make():
        conn = await aiosqlite.connect(str(tmp_path / "checkpoints.db"))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        savers.append(saver)
        return saver

    yield make

    for saver in savers:
        asyncio.run(saver.conn.close())


def test_chat_node_sends_system_prompt_and_history(monkeypatch) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="回答")
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )

    state = {
        "messages": [
            HumanMessage(content="第一问"),
            AIMessage(content="第一答"),
            HumanMessage(content="第二问"),
        ]
    }
    result = asyncio.run(_chat_node(state))

    assert result["messages"][-1].content == "回答"
    mock_llm.ainvoke.assert_awaited_once()
    sent = mock_llm.ainvoke.await_args.args[0]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == CHAT_SYSTEM_PROMPT
    assert len(sent) == 4  # system + 3 条历史
    assert sent[-1].content == "第二问"


def test_chat_node_includes_summary_when_present(monkeypatch) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="回答"))
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )

    result = asyncio.run(_chat_node({
        "messages": [HumanMessage(content="新问题")],
        "summary": "早期对话摘要",
    }))

    assert result["messages"][-1].content == "回答"
    sent = mock_llm.ainvoke.await_args.args[0]
    assert len(sent) == 3  # system + 摘要 + 新问题
    assert isinstance(sent[1], SystemMessage)
    assert "早期对话摘要" in sent[1].content


def test_summarize_node_noop_under_boundary(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chat_graph.TOKEN_BOUNDARY",
        10**9,
    )

    result = asyncio.run(_summarize_node({
        "messages": [HumanMessage(content="hi")],
        "summary": "",
    }))

    assert result == {}


def test_summarize_node_compresses_old_messages(monkeypatch) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="新的合并摘要")
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "app.services.chat_graph.TOKEN_BOUNDARY",
        1,  # 必然超阈值
    )

    messages = [
        HumanMessage(content=f"问题{i}", id=f"msg-{i}")
        for i in range(15)
    ]
    result = asyncio.run(_summarize_node({
        "messages": messages,
        "summary": "旧摘要",
    }))

    assert result["summary"] == "新的合并摘要"
    removes = result["messages"]
    assert all(isinstance(item, RemoveMessage) for item in removes)
    assert len(removes) == 5  # 15 条里保留最近 10 条，删最老的 5 条
    assert [r.id for r in removes] == [f"msg-{i}" for i in range(5)]

    mock_llm.ainvoke.assert_awaited_once()
    prompt = mock_llm.ainvoke.await_args.args[0]
    assert len(prompt) == 7  # 旧摘要 + 5 条老消息 + 压缩指令
    assert "旧摘要" in prompt[0].content
    assert "压缩" in prompt[-1].content


def test_summarize_node_compresses_all_when_under_keep_raw(monkeypatch) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="大消息摘要"))
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "app.services.chat_graph.TOKEN_BOUNDARY",
        1,  # 必然超阈值
    )

    # 消息数不超过 KEEP_RAW 但总 token 超阈值：全部压缩，不留原文
    messages = [
        HumanMessage(content=f"很长的问题内容{i}", id=f"big-{i}")
        for i in range(3)
    ]
    result = asyncio.run(_summarize_node({
        "messages": messages,
        "summary": "",
    }))

    assert result["summary"] == "大消息摘要"
    assert [r.id for r in result["messages"]] == ["big-0", "big-1", "big-2"]


def test_chat_graph_returns_latest_message(monkeypatch, temp_checkpointer) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content="答1"),
            AIMessage(content="答2"),
        ]
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_checkpointer",
        AsyncMock(side_effect=temp_checkpointer),
    )

    async def main() -> None:
        graph = await build_chat_graph()
        thread = {"configurable": {"thread_id": "chat-test-1"}}
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="问1")]},
            config=thread,
        )
        assert result["messages"][-1].content == "答1"

        # 第二轮：同一 thread，LLM 应收到完整历史
        result2 = await graph.ainvoke(
            {"messages": [HumanMessage(content="问2")]},
            config=thread,
        )
        assert result2["messages"][-1].content == "答2"
        sent = mock_llm.ainvoke.await_args.args[0]
        assert len(sent) == 4  # system + 问1 + 答1 + 问2

    asyncio.run(main())


def test_chat_graph_different_threads_are_isolated(
        monkeypatch, temp_checkpointer
) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="答"))
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_checkpointer",
        AsyncMock(side_effect=temp_checkpointer),
    )

    async def main() -> None:
        graph = await build_chat_graph()
        await graph.ainvoke(
            {"messages": [HumanMessage(content="线程A")]},
            config={"configurable": {"thread_id": "chat-a"}},
        )
        await graph.ainvoke(
            {"messages": [HumanMessage(content="线程B")]},
            config={"configurable": {"thread_id": "chat-b"}},
        )
        # 线程 A 再问一次，LLM 不应看到线程 B 的消息
        await graph.ainvoke(
            {"messages": [HumanMessage(content="线程A又来了")]},
            config={"configurable": {"thread_id": "chat-a"}},
        )
        sent = mock_llm.ainvoke.await_args.args[0]
        contents = [m.content for m in sent]
        assert sum("线程A" in c for c in contents) == 2
        assert "线程B" not in contents

    asyncio.run(main())


def test_chat_graph_summarize_removes_old_and_injects_summary(
        monkeypatch, temp_checkpointer
) -> None:
    """集成测试：经真实 checkpointer 验证摘要删除原文并注入第二轮。"""
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content="合并摘要"),  # 第一轮 summarize
            AIMessage(content="答1"),      # 第一轮 chat
            AIMessage(content="答2"),      # 第二轮 chat
        ]
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_llm",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "app.services.chat_graph.get_checkpointer",
        AsyncMock(side_effect=temp_checkpointer),
    )
    monkeypatch.setattr(
        "app.services.chat_graph.TOKEN_BOUNDARY",
        50,
    )

    long_question = "长问题" * 30  # 约 90 token，必然超 50 阈值

    async def main() -> None:
        graph = await build_chat_graph()
        thread = {"configurable": {"thread_id": "chat-summary-1"}}
        await graph.ainvoke(
            {"messages": [HumanMessage(content=long_question)]},
            config=thread,
        )
        result2 = await graph.ainvoke(
            {"messages": [HumanMessage(content="问题2")]},
            config=thread,
        )

        sent = mock_llm.ainvoke.await_args.args[0]
        contents = [m.content for m in sent]
        assert "合并摘要" in contents[1]           # 摘要注入在 system 之后
        assert not any(long_question in c for c in contents)  # 原文已删除
        assert "问题2" in contents[-1]             # 新消息保留
        assert result2["messages"][-1].content == "答2"

    asyncio.run(main())
