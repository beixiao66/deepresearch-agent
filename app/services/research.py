import logging

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


async def run_research(
        request: ResearchRequest,
        task_repository: ResearchTaskRepository,
) -> ResearchReport:
    """执行研究任务，并把状态持久化到 research_tasks 表。

    状态流转：pending(创建时) -> running(开始执行) -> completed/failed。
    """
    task = await task_repository.create(
        topic=request.topic,
        knowledge_base_id=request.knowledge_base_id,
    )

    await task_repository.session.commit()

    try:
        await task_repository.update_status(
            task,
            ResearchTaskStatus.RUNNING,
        )
        await task_repository.session.commit()

        graph = get_research_graph()
        result = await graph.ainvoke(
            {
                "question": request.topic,
                "knowledge_base_id": request.knowledge_base_id,
            }
        )

        sources = [
            {
                "document_id": source.get("document_id"),
                "chunk_index": source.get("chunk_index"),
                "text": source["text"],
                "score": source["score"],
                "query": source["query"],
            }
            for source in result["sources"]
        ]

        report = ResearchReport(
            topic=request.topic,
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
