"""LLM 调用封装：统一提取 token 用量。

各节点直接调用这些函数，返回内容与结果一致，同时把 usage 累加到
传入的计数器 dict 中，避免每个节点重复写提取逻辑。
"""
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.schemas.research import ResearchPlan


@lru_cache
def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
        model=settings.llm_model,
        temperature=0,
        timeout=120,
        max_retries=2,
    )


def _record_usage(counters: dict, response) -> None:
    """从响应中提取 token 用量并累加到计数器。

    counters 结构：
    {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    """
    metadata = getattr(response, "usage_metadata", None) or {}
    counters["prompt_tokens"] += metadata.get("input_tokens", 0)
    counters["completion_tokens"] += metadata.get("output_tokens", 0)
    counters["total_tokens"] += metadata.get("total_tokens", 0)


async def generate_research_plan(
        topic: str,
        usage_counters: dict | None = None,
) -> ResearchPlan:
    """生成研究计划（结构化输出），返回 plan 并累加 token 用量。"""
    messages = [
        SystemMessage(
            content=(
                "你是一名研究计划设计助手。"
                "请将用户的研究主题拆分为可检索、可验证的子问题。"
                "不要回答研究问题本身，只生成研究计划。"
            )
        ),
        HumanMessage(content=f"研究主题：{topic}"),
    ]

    result = await get_llm().with_structured_output(
        ResearchPlan,
        include_raw=True,
    ).ainvoke(messages)

    # include_raw=True 时返回 {"raw": AIMessage, "parsed": ResearchPlan, ...}
    if isinstance(result, dict):
        raw_message = result.get("raw")
        if usage_counters is not None and raw_message is not None:
            _record_usage(usage_counters, raw_message)
        return result.get("parsed")

    # 兜底：某些版本可能直接返回 plan
    if usage_counters is not None:
        _record_usage(usage_counters, result)
    return result


async def generate_follow_up_queries(
        question: str,
        source_count: int,
        usage_counters: dict | None = None,
) -> list[str]:
    """证据不足时生成补充查询词，返回关键词列表并累加 token 用量。"""
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
                f"研究问题：{question}\n"
                f"当前已检索：{source_count} 条资料"
            )
        ),
    ]

    response = await get_llm().ainvoke(messages)

    if usage_counters is not None:
        _record_usage(usage_counters, response)

    return [
        line.strip()
        for line in str(response.content).splitlines()
        if line.strip()
    ][:3]


async def generate_report(
        question: str,
        sources_text: str,
        usage_counters: dict | None = None,
) -> str:
    """生成研究报告，返回报告文本并累加 token 用量。"""
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
                f"研究问题：{question}\n\n"
                f"{sources_text}"
            )
        ),
    ]

    response = await get_llm().ainvoke(messages)

    if usage_counters is not None:
        _record_usage(usage_counters, response)

    return response.content
