import asyncio
from unittest.mock import AsyncMock, Mock

from app.services.sse import format_sse


def test_format_sse_produces_valid_message() -> None:
    message = format_sse({"type": "status", "message": "正在检索"})

    assert message.startswith("data: ")
    assert message.endswith("\n\n")
    assert "正在检索" in message


def test_format_sse_handles_unicode() -> None:
    message = format_sse({"type": "completed", "report": "研究报告✅"})

    assert "研究报告" in message
    assert "✅" in message


def test_stream_start_research_emits_events() -> None:
    async def run_test() -> None:
        from app.schemas.research import ResearchPlan
        from app.schemas.research_report import ResearchReport, ResearchRequest

        plan = ResearchPlan(
            topic="RAG",
            objective="研究 RAG",
            sub_questions=["什么是 RAG？"],
            search_queries=["RAG"],
        )

        task_repository = Mock()

        report = ResearchReport(
            topic="RAG",
            plan=plan,
            sources=[],
            answer="",
            task_id=42,
        )

        async def fake_start(request, task_repository):
            return report

        import app.services.sse as sse_module
        original = sse_module.start_research
        sse_module.start_research = fake_start
        try:
            events = []
            async for chunk in sse_module.stream_start_research(
                ResearchRequest(topic="RAG", knowledge_base_id=1),
                task_repository,
            ):
                events.append(chunk)

            assert len(events) == 2
            assert "task_created" in events[0]
            assert '"task_id": 42' in events[0]
            assert "awaiting_approval" in events[1]
        finally:
            sse_module.start_research = original

    asyncio.run(run_test())
