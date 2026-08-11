import logging

import anyio
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.schemas.state import ResearchState
from app.services.web_search import search_web
from app.db.session import AsyncSessionLocal
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
from app.services.reranker import get_reranker
from app.services.sparse_indexer import SparseIndexer
from app.services.sparse_retriever import SparseRetriever
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 进度事件钩子：SSE 时由服务层替换为实际发事件的回调
_progress_hook = None


def set_progress_hook(hook) -> None:
    """设置进度回调（接收 dict 事件）。SSE 流用，测试/普通调用不设。"""
    global _progress_hook
    _progress_hook = hook


def _emit(event: dict) -> None:
    if _progress_hook is not None:
        _progress_hook(event)


@lru_cache
def get_retriever() -> DocumentRetriever:
    """构建全局复用的检索器实例（向量路）。"""
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
    _emit({
        "type": "status",
        "stage": "plan",
        "message": "正在生成研究计划...",
    })
    plan = await generate_research_plan(state["question"])
    _emit({
        "type": "status",
        "stage": "plan",
        "message": "研究计划已生成",
    })
    return {
        "plan": plan,
        "knowledge_base_id": state["knowledge_base_id"],
        "use_web_search": state.get("use_web_search", False),
    }


def _review_plan(state: ResearchState) -> dict:
    """审核节点：interrupt 暂停，等用户确认或修改研究计划。

    注意：interrupt 前没有副作用操作（可安全重放）。
    """
    user_review = interrupt(
        {
            "title": "研究计划审核",
            "question": state["question"],
            "sub_questions": state["plan"].sub_questions,
            "search_queries": state["plan"].search_queries,
        }
    )

    approved = bool(user_review.get("approved"))

    if not approved:
        raise ValueError(
            "Research plan rejected by user"
        )

    return {"plan": state["plan"]}


async def _retrieve(state: ResearchState) -> dict:
    """检索节点：根据规划产出的关键词查询向量库，收集资料片段。"""
    logger.info("retrieve node: round %d", state.get("retrieval_round", 0) + 1)
    _emit({
        "type": "status",
        "stage": "retrieve",
        "message": "正在检索知识库...",
    })
    sources: list[dict] = []

    queries = state["plan"].search_queries
    if state.get("next_queries"):
        queries = state["next_queries"]

    # 混合检索：向量 + FTS5 + Rerank。
    # SparseRetriever 需要 session，session 生命周期 = 本节点执行周期。
    async with AsyncSessionLocal() as session:
        await SparseIndexer(session).ensure_table()

        retriever = DocumentRetriever(
            embedder=DocumentEmbedder(get_embedding_client()),
            qdrant_store=QdrantStore(
                client=get_qdrant_client(),
                collection_name=get_settings().qdrant_collection,
                vector_size=1024,
            ),
            sparse_retriever=SparseRetriever(session),
            reranker=get_reranker(),
        )

        for query in queries:
            results = await retriever.retrieve_hybrid(
                question=query,
                knowledge_base_id=state.get(
                    "knowledge_base_id",
                    1,
                ),
                limit=3,
                rerank=True,
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

    # 知识库证据不足且开启联网：补一轮 Tavily 搜索
    # 判定标准与证据评估一致：条数不足 或 平均分过低
    # 只在第一轮触发（round 0），避免每轮循环都重复联网
    is_first_round = state.get("retrieval_round", 0) == 0
    if is_first_round and state.get("use_web_search", False):
        evidence_insufficient = False

        if len(combined) < 3:
            evidence_insufficient = True
        elif combined:
            avg_score = sum(
                source.get("score", 0.0)
                for source in combined
            ) / len(combined)
            if avg_score < 0.3:
                evidence_insufficient = True

        if evidence_insufficient:
            logger.info(
                "knowledge base evidence insufficient, searching web"
            )
            _emit({
                "type": "status",
                "stage": "retrieve",
                "message": "知识库资料不足，正在联网搜索...",
            })
            for query in queries:
                web_results = await anyio.to_thread.run_sync(
                    search_web,
                    query,
                    3,
                )
                for web_result in web_results:
                    combined.append(
                        {
                            "document_id": None,
                            "chunk_index": None,
                            "text": web_result.content,
                            "score": web_result.score,
                            "query": query,
                            "source_type": "web",
                            "url": web_result.url,
                        }
                    )

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
    """条件边：评估证据充分性，充分则生成报告，否则继续检索（带轮次上限）。

    评估维度：
    - 条数：检索到的资料片段数
    - 平均分：片段的平均相关度（过低视为证据不足，即使条数够）
    """
    MIN_SOURCES = 3
    MAX_ROUNDS = 3
    MIN_AVG_SCORE = 0.3

    sources = state.get("sources", [])
    sources_count = len(sources)
    round_count = state.get("retrieval_round", 0)

    if sources_count >= MIN_SOURCES:
        avg_score = sum(
            source.get("score", 0.0)
            for source in sources
        ) / sources_count

        if avg_score >= MIN_AVG_SCORE:
            logger.info(
                "evidence sufficient (%d sources, avg %.2f), report",
                sources_count,
                avg_score,
            )
            return "report"

        logger.info(
            "evidence weak (avg %.2f < %.2f), continue",
            avg_score,
            MIN_AVG_SCORE,
        )
    else:
        logger.info(
            "not enough sources (%d < %d), continue",
            sources_count,
            MIN_SOURCES,
        )

    if round_count >= MAX_ROUNDS:
        logger.info("max rounds reached (%d), report", round_count)
        return "report"

    return "next_queries"

    if round_count >= MAX_ROUNDS:
        logger.info("max rounds reached (%d), report", round_count)
        return "report"

    logger.info("not enough sources (%d < %d), continue", sources_count, MIN_SOURCES)
    return "next_queries"


async def _report(state: ResearchState) -> dict:
    """报告节点：结合检索到的资料，生成最终研究报告。"""
    logger.info("report node")
    _emit({
        "type": "status",
        "stage": "report",
        "message": "正在生成研究报告...",
    })

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
    """构建 LangGraph 主流程：规划 -> 审核(人工确认) -> 检索 -> (条件循环) -> 报告。"""
    graph = StateGraph(ResearchState)

    graph.add_node("plan", _plan_research)
    graph.add_node("review", _review_plan)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("next_queries", _next_queries)
    graph.add_node("report", _report)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "review")
    graph.add_edge("review", "retrieve")
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

    # interrupt 需要 checkpoint 保存执行现场
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
