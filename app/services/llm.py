"""LLM 调用封装：统一提取 token 用量。

各节点直接调用这些函数，返回内容与结果一致，同时把 usage 累加到
传入的计数器 dict 中，避免每个节点重复写提取逻辑。
"""
import re
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.schemas.research import ResearchPlan


# chat 多轮对话系统提示词：有记忆后可基于历史给出建议
CHAT_SYSTEM_PROMPT = (
    "你是一名 AI 技术研究助手，正在进行多轮对话。"
    "请准确、简洁地回答用户问题；不确定时应明确说明，不要编造信息。"
    "根据对话历史与用户已表达的需求，可以主动给出进一步的研究方向、"
    "补充资料或实用建议。"
)


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
                "所有子问题和检索关键词都必须使用与研究主题相同的语言"
                "（主题是中文就全部用中文，主题是英文就全部用英文），"
                "不要混用语言，不要输出英文关键词。"
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


# 引用编号：形如 [1] 或 [1][2][3]
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")
# 区间引用：形如 [1]–[5] 或 [1]-[5]（模型常写"基于 [1]–[5]"）
_CITATION_RANGE_PATTERN = re.compile(
    r"\[(\d+)\]\s*[–—-]\s*\[(\d+)\]"
)
# 残缺区间：形如 [1]– 后面没有结束编号（如"基于 [1]–）"）
_CITATION_TRAILING_RANGE_PATTERN = re.compile(
    r"\[(\d+)\]\s*[–—-]\s*(?!\[)"
)
# 残留的空壳括号：形如（基于 ）或（基于），括号内只有"基于"
_EMPTY_BASED_PAREN_PATTERN = re.compile(
    r"[（(]\s*基于\s*[）)]"
)


def _strip_invalid_citations(text: str, max_citation: int) -> str:
    """删除超出来源数量的引用编号（模型可能编造不存在的 [n]）。

    处理三种情况：
    1. 单个编号 [5] 超范围 → 删除编号本身，保留正文
    2. 区间 [1]–[5] 结束编号超范围 → 截断为 [1]-[N]
    3. 残缺区间 [1]– 没有结束编号 → 整体删除，避免"有头没尾"
    """
    if max_citation <= 0:
        return text

    def fix_range(match: re.Match) -> str:
        start = int(match.group(1))
        end = int(match.group(2))
        if start > max_citation:
            return ""
        new_end = min(end, max_citation)
        return f"[{start}]-[{new_end}]"

    # 1. 完整区间：截断超范围结束编号
    text = _CITATION_RANGE_PATTERN.sub(fix_range, text)

    # 2. 残缺区间（[n]– 后无结束编号）：整体删除
    text = _CITATION_TRAILING_RANGE_PATTERN.sub("", text)

    # 3. 单个超范围编号
    def replace(match: re.Match) -> str:
        number = int(match.group(1))
        if number > max_citation:
            return ""
        return match.group(0)

    text = _CITATION_PATTERN.sub(replace, text)

    # 4. 清理残留空壳括号（基于 ）
    text = _EMPTY_BASED_PAREN_PATTERN.sub("", text)

    return text


async def generate_report(
        question: str,
        sources_text: str,
        usage_counters: dict | None = None,
        max_citation: int = 0,
) -> str:
    """生成研究报告，返回报告文本并累加 token 用量。

    生成后删除超出来源数量的引用编号（模型可能编造不存在的 [n]），
    避免报告出现无法承接的 [n] 引用。
    """
    messages = [
        SystemMessage(
            content=(
                "你是一名研究助手。请基于用户问题与检索到的资料，"
                "生成结构清晰、有据可依的研究报告。"
                "报告应包含：结论、关键证据（引用编号）、局限与参考来源。"
                f"资料编号范围是 [1] 到 [{max_citation}]，"
                "只能引用这个范围内的编号，绝对不要编造不存在的编号。"
                "每条结论最多引用 3-5 个最直接相关的编号，"
                "不要罗列全部编号，避免大段引用标记影响阅读。"
                "报告在结论、参考来源之后立即结束。"
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

    return _strip_invalid_citations(response.content, max_citation)


async def generate_sub_answer(
        sub_question: str,
        sources_text: str,
        usage_counters: dict | None = None,
) -> str:
    """子 Agent：针对单个子问题生成带证据的回答。"""
    messages = [
        SystemMessage(
            content=(
                "你是研究助手的一个子研究员。请只针对给定的子问题，"
                "基于检索到的资料给出有据可依的回答。"
                "回答应包含：核心结论、关键证据（引用编号）。"
                "每条结论最多引用 3-5 个最直接相关的编号，"
                "不要罗列全部编号。"
                "如果资料不足以回答，请明确说明'暂无足够资料'，"
                "不要编造内容。"
            )
        ),
        HumanMessage(
            content=(
                f"子问题：{sub_question}\n\n"
                f"{sources_text}"
            )
        ),
    ]

    response = await get_llm().ainvoke(messages)

    if usage_counters is not None:
        _record_usage(usage_counters, response)

    return response.content
