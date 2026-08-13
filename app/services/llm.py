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


# 报告末尾推荐性段落起始词：命中即截断（模型有时会自行添加"如需帮助"类内容）
_PROMOTIONAL_PATTERNS = [
    r"如需[，,。]?我",
    r"如果需要[，,。]?我",
    r"如您需要",
    r"若需",
    r"若您需要",
    r"请随时告知",
    r"欢迎随时",
    r"如果您有任何",
    r"我可以为您",
    r"我可以为你",
    r"有需要[，,。]?请",
]


def _strip_promotional_tail(text: str) -> str:
    """删除报告末尾的推荐性段落（模型自行添加的'如需帮助'类内容）。

    找到第一个匹配位置后，从该位置截断；同时清理截断点残留的
    空行和列表符号。
    """
    for pattern in _PROMOTIONAL_PATTERNS:
        match = re.search(pattern, text)
        if match:
            text = text[: match.start()]
            break

    return text.rstrip().rstrip("。；;").rstrip()


# 引用编号：形如 [1] 或 [1][2][3]
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def _strip_invalid_citations(text: str, max_citation: int) -> str:
    """删除超出来源数量的引用编号（模型可能编造不存在的 [n]）。

    只删除编号本身（如 [5]），保留正文文字。例如：
    "混合检索 [1][3][5]" → "混合检索 [1][3]"
    """
    if max_citation <= 0:
        return text

    def replace(match: re.Match) -> str:
        number = int(match.group(1))
        if number > max_citation:
            return ""
        return match.group(0)

    return _CITATION_PATTERN.sub(replace, text)


async def generate_report(
        question: str,
        sources_text: str,
        usage_counters: dict | None = None,
        max_citation: int = 0,
) -> str:
    """生成研究报告，返回报告文本并累加 token 用量。

    生成后过滤末尾的推荐性段落，并删除超出来源数量的引用编号，
    避免报告出现无法承接的 "如需帮助" 内容和编造的 [n] 引用。
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
                "报告在结论、参考来源之后立即结束，"
                "不要输出任何'如需帮助请联系我'、'我可以为您提供'、"
                "'请随时告知需求'之类的推荐、承诺或引导性内容，"
                "不要把模型能力宣传或后续服务建议写进报告。"
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

    cleaned = _strip_promotional_tail(response.content)
    return _strip_invalid_citations(cleaned, max_citation)


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
                "不要编造内容，不要输出任何'如需帮助'类推荐。"
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

    return _strip_promotional_tail(response.content)
