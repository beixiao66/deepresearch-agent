import logging

from app.schemas.research_report import ResearchReport, ResearchRequest
from app.services.research_graph import build_research_graph

logger = logging.getLogger(__name__)

_research_graph = None


def get_research_graph():
    global _research_graph

    if _research_graph is None:
        _research_graph = build_research_graph()

    return _research_graph


async def run_research(request: ResearchRequest) -> ResearchReport:
    graph = get_research_graph()

    result = await graph.ainvoke(
        {
            "question": request.topic,
            "knowledge_base_id": request.knowledge_base_id,
        }
    )

    logger.info(
        "research completed: sources=%d",
        len(result["sources"]),
    )

    return ResearchReport(
        topic=request.topic,
        plan=result["plan"],
        sources=[
            {
                "document_id": source.get("document_id"),
                "chunk_index": source.get("chunk_index"),
                "text": source["text"],
                "score": source["score"],
                "query": source["query"],
            }
            for source in result["sources"]
        ],
        answer=result["answer"],
    )
