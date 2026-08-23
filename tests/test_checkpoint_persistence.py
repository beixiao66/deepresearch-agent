"""持久化 checkpointer 测试：进程重启（重新打开数据库）后 checkpoint 仍可恢复。

替代 MemorySaver 的核心收益就是持久化：研究任务在 interrupt 暂停点保存的
执行现场，必须能在服务重启后通过同一 thread_id 恢复。
"""
import asyncio

import aiosqlite

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


def build_checkpoint() -> dict:
    return {
        "v": 1,
        "ts": "2026-08-22T00:00:00Z",
        "id": "checkpoint-1",
        "channel_values": {"question": "Agentic RAG"},
        "versions_seen": {},
        "pending_sends": [],
        "channel_versions": {},
    }


def test_checkpoint_persists_across_reopen(tmp_path) -> None:
    """写入 checkpoint 后关闭连接（模拟进程退出），重新打开同一文件可恢复。"""
    db_path = tmp_path / "checkpoints.db"

    async def main() -> None:
        # 第一次"进程"：写入 checkpoint 后关闭连接
        conn = await aiosqlite.connect(str(db_path))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()

        # checkpoint_ns 由 LangGraph 运行时自动注入，裸调用需手动给出
        config = {
            "configurable": {
                "thread_id": "research-1",
                "checkpoint_ns": "",
            }
        }
        await saver.aput(
            config,
            build_checkpoint(),
            {},
            {},
        )
        await conn.close()

        # 第二次"进程"：重新打开同一文件，按 thread_id 恢复
        conn2 = await aiosqlite.connect(str(db_path))
        saver2 = AsyncSqliteSaver(conn2)

        restored = await saver2.aget_tuple(config)

        await conn2.close()

        assert restored is not None
        assert restored.config["configurable"]["thread_id"] == "research-1"
        assert (
            restored.checkpoint["channel_values"]["question"]
            == "Agentic RAG"
        )

    asyncio.run(main())


def test_checkpoint_returns_none_for_unknown_thread(tmp_path) -> None:
    """未写入过 checkpoint 的 thread_id 返回 None（与 MemorySaver 行为一致）。"""
    db_path = tmp_path / "checkpoints.db"

    async def main() -> None:
        conn = await aiosqlite.connect(str(db_path))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()

        result = await saver.aget_tuple(
            {"configurable": {"thread_id": "never-exists"}}
        )

        await conn.close()

        assert result is None

    asyncio.run(main())


def test_checkpoint_tables_created_automatically(tmp_path) -> None:
    """setup 后建表，且重复 setup 幂等。"""
    db_path = tmp_path / "checkpoints.db"

    async def main() -> None:
        conn = await aiosqlite.connect(str(db_path))
        saver = AsyncSqliteSaver(conn)

        # 不手动调 setup，首次 aget_tuple 会自动建表
        result = await saver.aget_tuple(
            {"configurable": {"thread_id": "t"}}
        )
        assert result is None

        # 幂等：再次 setup 不报错
        await saver.setup()
        await saver.setup()

        await conn.close()

    asyncio.run(main())
