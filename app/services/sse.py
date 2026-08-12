"""SSE 流式研究执行：逐步推送进度事件。"""
import asyncio
import json
import logging

from app.core.exceptions import get_public_error
from app.repositories.research_task import ResearchTaskRepository
from app.schemas.research_report import (
    ResearchRequest,
)
from app.services.research import approve_research, start_research
from app.services.research_graph import set_progress_hook

logger = logging.getLogger(__name__)


def format_sse(event: dict) -> str:
    """把事件 dict 转成 SSE 消息格式。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _collect_events() -> asyncio.Queue:
    """创建事件队列并绑定到进度钩子。"""
    events_queue: asyncio.Queue = asyncio.Queue()

    def hook(event: dict) -> None:
        events_queue.put_nowait(event)

    set_progress_hook(hook)
    return events_queue


async def _drain_events(events_queue: asyncio.Queue):
    """把队列里累积的进度事件按序 yield 出去。"""
    while not events_queue.empty():
        yield format_sse(events_queue.get_nowait())


async def _cleanup_temp_knowledge_base(
        task_id: int,
        task_repository: ResearchTaskRepository,
        knowledge_base_service,
        temp_kb_prefix: str,
) -> None:
    """研究任务结束后，删除上传附件时创建的临时知识库。

    临时知识库只在任务执行期间存在，任务完成/取消/失败后自动清理，
    不会留在知识库列表中。
    """
    try:
        task = await task_repository.get_by_id(task_id)
        if task is None:
            return

        knowledge_base = await knowledge_base_service.get_by_id(
            task.knowledge_base_id
        )
        if (
            knowledge_base is not None
            and knowledge_base.name.startswith(temp_kb_prefix)
        ):
            await knowledge_base_service.delete(
                task.knowledge_base_id
            )
            logger.info(
                "temp knowledge base cleaned: kb_id=%d",
                task.knowledge_base_id,
            )
    except Exception as exc:
        logger.error(
            "temp knowledge base cleanup failed: task_id=%d, error=%s",
            task_id,
            exc,
            exc_info=True,
        )


async def stream_start_research(
        request: ResearchRequest,
        task_repository: ResearchTaskRepository,
        knowledge_base_service=None,
        temp_kb_prefix: str | None = None,
):
    """SSE 流（阶段一）：创建任务 → 生成计划 → 暂停等确认。"""
    events_queue = await _collect_events()

    try:
        # start_research 内部创建任务、跑图到 interrupt 暂停
        report = await start_research(request, task_repository)

        yield format_sse({
            "type": "task_created",
            "task_id": report.task_id,
            "message": "研究任务已创建",
        })

        async for event in _drain_events(events_queue):
            yield event

        yield format_sse({
            "type": "awaiting_approval",
            "stage": "review",
            "message": "研究计划已生成，等待确认",
        })
    except Exception as exc:
        error = get_public_error(exc)
        logger.error(
            "Research start stream failed: error=%s",
            exc,
            exc_info=True,
        )
        yield format_sse({
            "type": "error",
            "code": error.code,
            "message": error.message,
        })

    finally:
        set_progress_hook(None)


async def stream_approve_research(
        task_id: int,
        approved: bool,
        task_repository: ResearchTaskRepository,
        knowledge_base_service=None,
        temp_kb_prefix: str | None = None,
):
    """SSE 流（阶段二）：批准后执行检索与报告。"""
    events_queue = await _collect_events()

    try:
        report = await approve_research(
            task_id,
            approved,
            task_repository,
        )

        async for event in _drain_events(events_queue):
            yield event

        if not approved:
            yield format_sse({
                "type": "cancelled",
                "task_id": task_id,
                "message": "用户已取消此次研究任务",
            })
            return

        yield format_sse({
            "type": "completed",
            "task_id": task_id,
            "report": report.answer,
        })
    except Exception as exc:
        error = get_public_error(exc)
        logger.error(
            "Research approval stream failed: task_id=%d, error=%s",
            task_id,
            exc,
            exc_info=True,
        )
        yield format_sse({
            "type": "error",
            "code": error.code,
            "message": error.message,
        })

    finally:
        set_progress_hook(None)

        if knowledge_base_service is not None and temp_kb_prefix:
            await _cleanup_temp_knowledge_base(
                task_id,
                task_repository,
                knowledge_base_service,
                temp_kb_prefix,
            )
