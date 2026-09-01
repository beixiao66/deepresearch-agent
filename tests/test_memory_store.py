import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from app.services import memory_store
from langgraph.store.sqlite.aio import AsyncSqliteStore


def test_get_preferences_returns_defaults_when_empty(monkeypatch) -> None:
    fake_store = AsyncMock()
    fake_store.aget = AsyncMock(return_value=None)
    monkeypatch.setattr(
        memory_store,
        "get_store",
        AsyncMock(return_value=fake_store),
    )

    prefs = asyncio.run(memory_store.get_preferences())

    assert prefs == {"report_style": "detailed", "report_language": "zh"}
    fake_store.aget.assert_awaited_once_with(
        ("user", "1", "preferences"), "preferences"
    )


def test_save_and_read_preferences(monkeypatch) -> None:
    saved: dict = {}

    async def fake_aget(namespace, key):
        if saved:
            return SimpleNamespace(value=dict(saved))
        return None

    fake_store = AsyncMock()
    fake_store.aget = fake_aget
    fake_store.aput = AsyncMock(
        side_effect=lambda ns, k, v: saved.update(v)
    )
    monkeypatch.setattr(
        memory_store,
        "get_store",
        AsyncMock(return_value=fake_store),
    )

    asyncio.run(memory_store.save_preferences(
        1, {"report_style": "concise", "report_language": "zh"}
    ))
    prefs = asyncio.run(memory_store.get_preferences(1))

    assert prefs == {"report_style": "concise", "report_language": "zh"}
    fake_store.aput.assert_awaited_once_with(
        ("user", "1", "preferences"), "preferences",
        {"report_style": "concise", "report_language": "zh"},
    )


def test_get_research_history_returns_empty_when_none(monkeypatch) -> None:
    fake_store = AsyncMock()
    fake_store.aget = AsyncMock(return_value=None)
    monkeypatch.setattr(
        memory_store,
        "get_store",
        AsyncMock(return_value=fake_store),
    )

    history = asyncio.run(memory_store.get_research_history())

    assert history == []
    fake_store.aget.assert_awaited_once_with(
        ("user", "1", "history"), "research_history"
    )


def test_append_research_history_trims_to_20(monkeypatch) -> None:
    current: list[dict] = []

    async def fake_aget(namespace, key):
        return SimpleNamespace(value=list(current)) if current else None

    fake_store = AsyncMock()
    fake_store.aget = fake_aget
    fake_store.aput = AsyncMock(
        side_effect=lambda ns, k, v: current.clear() or current.extend(v)
    )
    monkeypatch.setattr(
        memory_store,
        "get_store",
        AsyncMock(return_value=fake_store),
    )

    for index in range(25):
        asyncio.run(memory_store.append_research_history(
            1, {"topic": f"主题{index}", "task_id": index}
        ))

    assert len(current) == 20
    assert current[0]["topic"] == "主题5"
    assert current[-1]["topic"] == "主题24"


def test_real_store_roundtrip(tmp_path) -> None:
    """真实 AsyncSqliteStore 落盘读写验证（API 契约测试）。"""

    async def main() -> None:
        # 与 memory_store.get_store 一致：AsyncSqliteStore 需 autocommit 连接
        conn = await aiosqlite.connect(
            str(tmp_path / "memory.db"), isolation_level=None
        )
        store = AsyncSqliteStore(conn)
        await store.setup()

        await store.aput(
            ("user", "1", "preferences"),
            "preferences",
            {"report_style": "concise", "report_language": "en"},
        )
        item = await store.aget(
            ("user", "1", "preferences"), "preferences"
        )
        assert item.value == {
            "report_style": "concise",
            "report_language": "en",
        }

        await conn.close()

    asyncio.run(main())
