import logging

from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.schemas.state import ResearchState
from app.services.document_embedder import (
    DocumentEmbedder,
    get_embedding_client,
)
from app.services.document_retriever import DocumentRetriever
from app.services.llm import get_llm
from app.services.planner import generate_research_plan
from app.services.qdrant_store import (
    QdrantStore,
    get_qdrant_client,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_retriever() -> DocumentRetriever:
    """构建全局复用的检索器实例（含 embedding 客户端）。"""
    settings = get_settings()

    return DocumentRetriever(
        embedder=DocumentEmbedder(get_embedding_client()),
        qdrant_store=QdrantStore(
            client=get_qdrant_client(),
            collection_name=settings.qdrant_collection,
            vector_size=1024,
        ),
    )


async def _plan_research(state: ResearchState) -> dict:
    """规划节点：把研究主题拆分为子问题与检索关键词。"""
    logger.info("plan node: %s", state["question"])
    plan = await generate_research_plan(state["question"])
    return {
        "plan": plan,
        "knowledge_base_id": state["knowledge_base_id"],
    }


async def _retrieve(state: ResearchState) -> dict:
    """检索节点：根据规划产出的关键词查询向量库，收集资料片段。"""
    logger.info("retrieve node: round %d", state.get("retrieval_round", 0) + 1)
    retriever = get_retriever()
    sources: list[dict] = []

    queries = state["plan"].search_queries
    if state.get("next_queries"):
        queries = state["next_queries"]

    for query in queries:
        results = await retriever.retrieve(
            question=query,
            knowledge_base_id=state.get(
                "knowledge_base_id",
                1,
            ),
            limit=3,
        )
        for result in results:
            sources.append(
                {
                    "document_id": result.document_id,
                    "chunk_index": result.chunk_index,
                    "text": result.text,
                    "score": result.score,
                    "query": query,
                }
            )

    existing = state.get("sources", [])
    combined = existing + sources

    logger.info("retrieved %d new sources, total %d", len(sources), len(combined))
    return {
        "sources": combined,
        "retrieval_round": state.get("retrieval_round", 0) + 1,
    }


async def _next_queries(state: ResearchState) -> dict:
    """补充查询节点：检索不足时，让 LLM 生成新一轮更精准的查询词。"""
    logger.info("next_queries node: generating follow-up queries")
    messages = [
        SystemMessage(
            content=(
                "你是研究助手。当前检索到的资料不足以回答研究问题，"
                "请生成3个与问题相关的补充检索关键词，"
                "每个关键词独立一行，不要编号。"
            )
        ),
        HumanMessage(
            content=(
                f"研究问题：{state['question']}\n"
                f"当前已检索：{len(state.get('sources', []))} 条资料"
            )
        ),
    ]

    response = await get_llm().ainvoke(messages)
    new_queries = [
        line.strip()
        for line in str(response.content).splitlines()
        if line.strip()
    ][:3]

    logger.info("follow-up queries: %s", new_queries)
    return {"next_queries": new_queries}


def _should_continue(state: ResearchState) -> str:
    """条件边：检索充分则生成报告，否则继续检索（带轮次上限）。"""
    MIN_SOURCES = 3
    MAX_ROUNDS = 3

    sources_count = len(state.get("sources", []))
    round_count = state.get("retrieval_round", 0)

    if sources_count >= MIN_SOURCES:
        logger.info("enough sources (%d >= %d), report", sources_count, MIN_SOURCES)
        return "report"

    if round_count >= MAX_ROUNDS:
        logger.info("max rounds reached (%d), report", round_count)
        return "report"

    logger.info("not enough sources (%d < %d), continue", sources_count, MIN_SOURCES)
    return "next_queries"


async def _report(state: ResearchState) -> dict:
    """报告节点：结合检索到的资料，生成最终研究报告。"""
    logger.info("report node")

    if state.get("sources"):
        sources_text = "\n".join(
            f"[{index}] {source['text']}"
            for index, source in enumerate(
                state["sources"],
                start=1,
            )
        )
        context = (
            f"检索资料：\n{sources_text}"
        )
    else:
        context = "（没有检索到资料，请基于自身知识作答）"

    messages = [
        SystemMessage(
            content=(
                "你是一名研究助手。请基于用户问题与检索到的资料，"
                "生成结构清晰、有据可依的研究报告。"
                "报告应包含：结论、关键证据（引用编号）、局限与参考来源。"
            )
        ),
        HumanMessage(
            content=(
                f"研究问题：{state['question']}\n\n"
                f"{context}"
            )
        ),
    ]

    response = await get_llm().ainvoke(messages)
    return {"answer": response.content}


def build_research_graph():
    """构建 LangGraph 主流程：规划 -> 检索 -> (条件判断循环) -> 报告。"""
    graph = StateGraph(ResearchState)

    graph.add_node("plan", _plan_research)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("next_queries", _next_queries)
    graph.add_node("report", _report)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        _should_continue,
        {
            "report": "report",
            "next_queries": "next_queries",
        },
    )
    graph.add_edge("next_queries", "retrieve")
    graph.add_edge("report", END)

    return graph.compile()
