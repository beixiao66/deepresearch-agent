"""长期记忆存储层：AsyncSqliteStore 单例 + 偏好/研究历史读写。

与 research_graph.get_checkpointer 同一套单例模式：aiosqlite 连接
常驻进程，首次调用时建表，应用关闭时 close_memory_store 关闭连接。
"""
import asyncio
import logging
import os

import aiosqlite
from langgraph.store.sqlite.aio import AsyncSqliteStore

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES = {
    "report_style": "detailed",
    "report_language": "zh",
}

_store: AsyncSqliteStore | None = None

# 并发研究任务同时完成时，append 是读-改-写，需串行化避免丢条目
_history_lock = asyncio.Lock()


async def get_store() -> AsyncSqliteStore:
    """构建全局复用的长期记忆 Store（AsyncSqliteStore 单例）。"""
    global _store
    if _store is None:
        settings = get_settings()
        db_dir = os.path.dirname(settings.memory_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # autocommit 模式（isolation_level=None）：AsyncSqliteStore 内部
        # 自行 BEGIN/COMMIT 管理事务（同 from_conn_string 的用法），
        # 用 sqlite3 默认延迟事务会报 "cannot start a transaction within a transaction"
        conn = await aiosqlite.connect(
            settings.memory_db_path, isolation_level=None
        )
        store = AsyncSqliteStore(conn)
        await store.setup()

        _store = store
        logger.info(
            "memory store initialized: %s",
            settings.memory_db_path,
        )
    return _store


async def close_memory_store() -> None:
    """应用关闭时关闭 store 连接（避免 aiosqlite 后台线程阻止进程退出）。"""
    global _store
    if _store is not None:
        await _store.conn.close()
        _store = None
        logger.info("memory store closed")


def _preferences_namespace(user_id: int) -> tuple[str, str, str]:
    return ("user", str(user_id), "preferences")


def _history_namespace(user_id: int) -> tuple[str, str, str]:
    return ("user", str(user_id), "history")


async def get_preferences(user_id: int = 1) -> dict:
    store = await get_store()
    item = await store.aget(_preferences_namespace(user_id), "preferences")
    if item is None:
        return dict(DEFAULT_PREFERENCES)
    # 旧数据缺字段时用默认值补齐，避免响应校验 500
    return {**DEFAULT_PREFERENCES, **item.value}


async def save_preferences(user_id: int, preferences: dict) -> None:
    store = await get_store()
    await store.aput(
        _preferences_namespace(user_id),
        "preferences",
        preferences,
    )


async def get_research_history(user_id: int = 1) -> list[dict]:
    store = await get_store()
    item = await store.aget(_history_namespace(user_id), "research_history")
    if item is None:
        return []
    return item.value


async def append_research_history(
        user_id: int,
        entry: dict,
        max_entries: int = 20,
) -> None:
    async with _history_lock:
        history = await get_research_history(user_id)
        history.append(entry)
        store = await get_store()
        await store.aput(
            _history_namespace(user_id),
            "research_history",
            history[-max_entries:],
        )
