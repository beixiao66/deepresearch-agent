from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.schemas.research import ResearchPlan


def add_sub_answers(
        left: list[dict] | None,
        right: list[dict] | None,
) -> list[dict]:
    """子 Agent 回答合并：多个子 Agent 并行返回时逐个追加。"""
    return (left or []) + (right or [])


def merge_token_usage(
        left: dict | None,
        right: dict | None,
) -> dict:
    """token 用量合并：多 Agent 并行时把各子 Agent 的用量累加。"""
    merged: dict = {}

    for usage in (left or {}, right or {}):
        for stage, counters in usage.items():
            stage_usage = merged.setdefault(
                stage,
                {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            )
            stage_usage["prompt_tokens"] += counters.get(
                "prompt_tokens", 0
            )
            stage_usage["completion_tokens"] += counters.get(
                "completion_tokens", 0
            )
            stage_usage["total_tokens"] += counters.get(
                "total_tokens", 0
            )

    return merged


class ResearchState(TypedDict):
    """LangGraph 图节点间共享的状态。"""
    question: str
    knowledge_base_id: int
    use_web_search: bool
    plan: ResearchPlan
    # 各子 Agent 的回答（并行分发后按顺序聚合）
    sub_answers: Annotated[list[dict], add_sub_answers]
    # 汇总后的完整报告
    answer: str
    # 报告使用的精选证据（每子问题 Top-K 去重后，与正文引用编号一一对应）
    curated_sources: list[dict]
    # token 用量（各节点/子 Agent 用量按阶段累加）
    token_usage: Annotated[dict, merge_token_usage]
    messages: Annotated[list[AnyMessage], add_messages]
