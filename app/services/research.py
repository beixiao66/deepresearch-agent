import logging

from langgraph.types import Command

from app.models.research_task import ResearchTaskStatus
from app.repositories.research_task import ResearchTaskRepository
from app.schemas.research_report import (
    ResearchReport,
    ResearchRequest,
)
from app.services.research_graph import build_research_graph

logger = logging.getLogger(__name__)

_research_graph = None


def get_research_graph():
    global _research_graph

    if _research_graph is None:
        _research_graph = build_research_graph()

    return _research_graph


def _build_thread_id(task_id: int) -> dict:
    """构建 checkpoint 的 thread 配置。

    thread_id 用任务 id，保证暂停后能用同一 thread 恢复执行现场。
    """
    return {
        "configurable": {
            "thread_id": f"research-{task_id}",
        }
    }


async def start_research(
        request: ResearchRequest,
        task_repository: ResearchTaskRepository,
) -> ResearchReport:
    """阶段一：创建任务，跑图到计划审核点暂停。"""
    task = await task_repository.create(
        topic=request.topic,
        knowledge_base_id=request.knowledge_base_id,
    )
    await task_repository.session.commit()

    graph = get_research_graph()

    try:
        await task_repository.update_status(
            task,
            ResearchTaskStatus.RUNNING,
        )
        await task_repository.session.commit()

        # 第一次 invoke：图跑到 review 节点的 interrupt 处暂停
        # ainvoke 返回中断时的状态快照（含 plan）
        result = await graph.ainvoke(
            {
                "question": request.topic,
                "knowledge_base_id": request.knowledge_base_id,
                "use_web_search": request.use_web_search,
            },
            config=_build_thread_id(task.id),
        )

        plan = result.get("plan")

        await task_repository.save_plan(
            task,
            plan=(
                plan.model_dump_json()
                if plan is not None
                else None
            ),
            thread_id=f"research-{task.id}",
        )
        await task_repository.session.commit()

        logger.info(
            "research paused at plan review: task_id=%d",
            task.id,
        )
    except Exception as exc:
        await task_repository.update_status(
            task,
            ResearchTaskStatus.FAILED,
            error_message=str(exc),
        )
        await task_repository.session.commit()
        logger.error(
            "research start failed: task_id=%d, error=%s",
            task.id,
            exc,
            exc_info=True,
        )
        raise

    return ResearchReport(
        topic=request.topic,
        plan=plan,
        sources=[],
        answer="",
    )


async def approve_research(
        task_id: int,
        approved: bool,
        task_repository: ResearchTaskRepository,
) -> ResearchReport:
    """阶段二：用户确认计划后，恢复图执行检索与报告。"""
    task = await task_repository.get_by_id(task_id)

    if task is None:
        from app.core.exceptions import DocumentNotFoundError
        raise DocumentNotFoundError(task_id)

    if task.status != ResearchTaskStatus.AWAITING_APPROVAL.value:
        raise ValueError(
            f"Task is not awaiting approval: {task.status}"
        )

    graph = get_research_graph()

    try:
        await task_repository.update_status(
            task,
            ResearchTaskStatus.RUNNING,
        )
        await task_repository.session.commit()

        # 第二次 invoke：Command(resume=...) 从 interrupt 处恢复
        result = await graph.ainvoke(
            Command(resume={"approved": approved}),
            config=_build_thread_id(task.id),
        )

        if not approved:
            # 拒绝：标记 failed（或者可以有 rejected 状态）
            await task_repository.update_status(
                task,
                ResearchTaskStatus.FAILED,
                error_message="Research plan rejected by user",
            )
            await task_repository.session.commit()

            return ResearchReport(
                topic=task.topic,
                plan=result["plan"],
                sources=[],
                answer="",
            )

        sources = [
            {
                "document_id": source.get("document_id"),
                "chunk_index": source.get("chunk_index"),
                "text": source["text"],
                "score": source["score"],
                "query": source["query"],
                "source_type": source.get(
                    "source_type",
                    "kb",
                ),
                "url": source.get("url"),
            }
            for source in result["sources"]
        ]

        report = ResearchReport(
            topic=task.topic,
            plan=result["plan"],
            sources=sources,
            answer=result["answer"],
        )

        await task_repository.save_report(
            task,
            result["answer"],
        )
        await task_repository.session.commit()

        logger.info(
            "research completed: task_id=%d, sources=%d",
            task.id,
            len(sources),
        )

        return report

    except Exception as exc:
        await task_repository.update_status(
            task,
            ResearchTaskStatus.FAILED,
            error_message=str(exc),
        )
        await task_repository.session.commit()
        logger.error(
            "research failed: task_id=%d, error=%s",
            task.id,
            exc,
            exc_info=True,
        )
        raise
