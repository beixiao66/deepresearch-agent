import asyncio
import logging

import anyio
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt

from app.schemas.state import ResearchState
from app.services.web_search import search_web
from app.db.session import AsyncSessionLocal
from app.services.document_embedder import (
    DocumentEmbedder,
    get_embedding_client,
)
from app.services.document_retriever import DocumentRetriever
from app.services.llm import (
    generate_report,
    generate_sub_answer,
    get_llm,
)
from app.services.planner import generate_research_plan
from app.services.qdrant_store import (
    QdrantStore,
    get_qdrant_client,
)
from app.services.reranker import get_reranker
from app.services.sparse_indexer import SparseIndexer
from app.services.sparse_retriever import SparseRetriever
from app.services.source_dedup import select_top_per_sub_question
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
    plan_counters = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    plan = await generate_research_plan(
        state["question"],
        plan_counters,
    )
    _emit({
        "type": "status",
        "stage": "plan",
        "message": "研究计划已生成",
    })
    return {
        "plan": plan,
        "knowledge_base_id": state["knowledge_base_id"],
        "use_web_search": state.get("use_web_search", False),
        "token_usage": {
            "plan": plan_counters,
        },
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


def _dispatch(state: ResearchState) -> dict:
    """分发节点占位：实际并行分发逻辑在条件边函数 _fanout 中。

    LangGraph 中 Send 列表必须由条件边函数返回，节点函数只返回
    状态更新（这里无需更新，返回空 dict）。
    """
    logger.info(
        "dispatch node: %d sub-questions",
        len(state["plan"].sub_questions),
    )
    _emit({
        "type": "status",
        "stage": "retrieve",
        "message": (
            f"正在并行研究 {len(state['plan'].sub_questions)} "
            "个子问题..."
        ),
    })
    return {}


def _fanout(state: ResearchState) -> list[Send]:
    """条件边函数：把每个子问题并行分发给独立的子研究员 Agent。

    返回 Send 列表，LangGraph 会并行执行所有 researcher 子 Agent，
    全部完成后才进入 report 聚合节点。
    """
    sub_questions = state["plan"].sub_questions
    logger.info(
        "fanout: %d sub-questions to researchers",
        len(sub_questions),
    )

    return [
        Send(
            "researcher",
            {
                "question": sub_question,
                "knowledge_base_id": state["knowledge_base_id"],
                "use_web_search": state.get("use_web_search", False),
                "plan": state["plan"],
            },
        )
        for sub_question in sub_questions
    ]


async def _researcher(state: ResearchState) -> dict:
    """子研究员 Agent：检索单个子问题的证据并生成子回答。"""
    sub_question = state["question"]
    logger.info("researcher agent: %s", sub_question)

    sources: list[dict] = []
    queries = state["plan"].search_queries

    # 混合检索：向量 + FTS5 + Rerank（子问题自身的检索路）
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

        # 用子问题本身作为查询词检索（子问题语义更聚焦）
        search_questions = [sub_question] + [
            query
            for query in queries
            if query not in (sub_question,)
        ]

        async def retrieve_one(query: str) -> list[dict]:
            results = await retriever.retrieve_hybrid(
                question=query,
                knowledge_base_id=state["knowledge_base_id"],
                limit=3,
                rerank=True,
            )
            return [
                {
                    "document_id": result.document_id,
                    "chunk_index": result.chunk_index,
                    "text": result.text,
                    "score": result.score,
                    "query": query,
                }
                for result in results
            ]

        results_per_query = await asyncio.gather(
            *[retrieve_one(query) for query in search_questions]
        )
        for query_results in results_per_query:
            sources.extend(query_results)

    # 证据不足且开启联网：补一轮 Tavily 搜索
    if state.get("use_web_search", False) and len(sources) < 3:
        _emit({
            "type": "status",
            "stage": "retrieve",
            "message": f"子问题证据不足，正在联网搜索: {sub_question[:20]}...",
        })
        for query in search_questions[:2]:
            web_results = await anyio.to_thread.run_sync(
                search_web,
                query,
                3,
            )
            for web_result in web_results:
                sources.append(
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

    # 生成子回答
    sub_counters = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    if not sources:
        answer = (
            "## 暂无足够资料\n\n"
            f"针对子问题「{sub_question}」，当前知识库中没有检索到"
            "相关内容，因此无法给出有据可依的回答。"
        )
    else:
        # 子回答只取 Top-5 证据，避免引用编号过多
        top_sources = sorted(
            sources,
            key=lambda source: source.get("score", 0.0),
            reverse=True,
        )[:5]
        sources_text = "\n".join(
            f"[{index}] {source['text']}"
            for index, source in enumerate(
                top_sources,
                start=1,
            )
        )
        answer = await generate_sub_answer(
            sub_question,
            f"检索资料：\n{sources_text}",
            sub_counters,
        )

    return {
        "sub_answers": [
            {
                "question": sub_question,
                "answer": answer,
                "sources": sources,
            }
        ],
        "token_usage": {
            "researcher": sub_counters,
        },
    }


async def _report(state: ResearchState) -> dict:
    """聚合节点：收集所有子 Agent 的回答，生成最终研究报告。"""
    logger.info("report node")
    _emit({
        "type": "status",
        "stage": "report",
        "message": "正在汇总子问题并生成研究报告...",
    })

    sub_answers = state.get("sub_answers", [])
    if not sub_answers:
        return {
            "answer": (
                "## 暂无足够资料\n\n"
                "当前没有生成任何子问题的研究结果，"
                "因此无法给出完整报告。\n\n"
                "> 本次未使用模型自身知识补充答案，以避免生成未经资料支持的内容。"
            )
        }

    # 汇总所有子回答 + 证据
    sub_answers_text = "\n\n".join(
        f"## 子问题 {index}：{item['question']}\n\n{item['answer']}"
        for index, item in enumerate(sub_answers, start=1)
    )

    # 每个子问题按相关度取 Top-K 证据，合并去重后作为报告引用来源。
    # 精选集合写入 state，保证正文引用编号与持久化来源一一对应。
    curated_sources = select_top_per_sub_question(
        sub_answers,
        top_k=5,
    )

    sources_text = "\n".join(
        f"[{index}] {source['text']}"
        for index, source in enumerate(
            curated_sources,
            start=1,
        )
    )
    context = (
        f"子问题研究结果：\n{sub_answers_text}\n\n"
        f"原始检索资料：\n{sources_text}"
    )

    report_counters = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    answer = await generate_report(
        state["question"],
        context,
        report_counters,
        max_citation=len(curated_sources),
    )
    return {
        "answer": answer,
        "curated_sources": curated_sources,
        "token_usage": {
            "report": report_counters,
        },
    }


def build_research_graph():
    """构建多 Agent 主流程：

    规划 -> 审核(人工确认) -> 分发(并行子研究员) -> 聚合报告。
    """
    graph = StateGraph(ResearchState)

    graph.add_node("plan", _plan_research)
    graph.add_node("review", _review_plan)
    graph.add_node("dispatch", _dispatch)
    graph.add_node("researcher", _researcher)
    graph.add_node("report", _report)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "review")
    graph.add_edge("review", "dispatch")
    # 条件边函数 _fanout 返回 Send 列表：并行启动所有 researcher
    # 子 Agent，全部完成后才进入 report
    graph.add_conditional_edges(
        "dispatch",
        _fanout,
        ["researcher"],
    )
    graph.add_edge("researcher", "report")
    graph.add_edge("report", END)

    # interrupt 需要 checkpoint 保存执行现场
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)
