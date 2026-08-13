import asyncio
from unittest.mock import AsyncMock, Mock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.schemas.research import ResearchPlan
from app.services.llm import (
    _strip_promotional_tail,
    generate_follow_up_queries,
    generate_report,
    generate_research_plan,
)


def build_plan() -> ResearchPlan:
    return ResearchPlan(
        topic="Agentic RAG",
        objective="研究 Agentic RAG",
        sub_questions=["Agentic RAG 是什么？"],
        search_queries=["Agentic RAG"],
    )


def build_ai_message(
        content: str,
        input_tokens: int = 10,
        output_tokens: int = 5,
) -> AIMessage:
    message = AIMessage(content=content)
    message.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    return message


def test_generate_research_plan_records_usage(
        monkeypatch,
) -> None:
    raw_message = build_ai_message(
        "plan",
        input_tokens=100,
        output_tokens=50,
    )
    result = {
        "raw": raw_message,
        "parsed": build_plan(),
        "parsing_error": None,
    }

    mock_llm = Mock()
    mock_llm.with_structured_output = Mock(
        return_value=Mock(ainvoke=AsyncMock(return_value=result))
    )

    monkeypatch.setattr(
        "app.services.llm.get_llm",
        lambda: mock_llm,
    )

    counters = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    plan = asyncio.run(
        generate_research_plan("Agentic RAG", counters)
    )

    assert plan == build_plan()
    assert counters == {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    }
    mock_llm.with_structured_output.assert_called_once_with(
        ResearchPlan,
        include_raw=True,
    )


def test_generate_research_plan_without_counters(
        monkeypatch,
) -> None:
    result = {
        "raw": build_ai_message("plan"),
        "parsed": build_plan(),
        "parsing_error": None,
    }

    mock_llm = Mock()
    mock_llm.with_structured_output = Mock(
        return_value=Mock(ainvoke=AsyncMock(return_value=result))
    )

    monkeypatch.setattr(
        "app.services.llm.get_llm",
        lambda: mock_llm,
    )

    plan = asyncio.run(
        generate_research_plan("Agentic RAG")
    )

    assert plan == build_plan()


def test_generate_follow_up_queries_records_usage(
        monkeypatch,
) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=build_ai_message(
            "RAG 原理\nRAG 架构\nRAG 应用",
            input_tokens=20,
            output_tokens=10,
        )
    )

    monkeypatch.setattr(
        "app.services.llm.get_llm",
        lambda: mock_llm,
    )

    counters = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    queries = asyncio.run(
        generate_follow_up_queries(
            "什么是 RAG？",
            2,
            counters,
        )
    )

    assert queries == ["RAG 原理", "RAG 架构", "RAG 应用"]
    assert counters == {
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "total_tokens": 30,
    }
    messages = mock_llm.ainvoke.await_args.args[0]
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "当前已检索：2 条资料" in messages[1].content


def test_generate_report_records_usage(
        monkeypatch,
) -> None:
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=build_ai_message(
            "研究报告内容",
            input_tokens=300,
            output_tokens=200,
        )
    )

    monkeypatch.setattr(
        "app.services.llm.get_llm",
        lambda: mock_llm,
    )

    counters = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    answer = asyncio.run(
        generate_report(
            "什么是 RAG？",
            "检索资料：\n[1] RAG 相关内容",
            counters,
        )
    )

    assert answer == "研究报告内容"
    assert counters == {
        "prompt_tokens": 300,
        "completion_tokens": 200,
        "total_tokens": 500,
    }


def test_strip_promotional_tail_removes_next_step_section() -> None:
    report = (
        "## 结论\n\n简历整体结构完整，技术栈匹配目标岗位。\n\n"
        "## 参考来源\n\n[1] 简历正文\n\n"
        "如需，我可为您：\n\n"
        "生成一份优化后的 Markdown 简历模板；\n"
        "撰写 STAR 描述稿。\n"
        "请随时告知您的进一步需求。"
    )

    cleaned = _strip_promotional_tail(report)

    assert "如需" not in cleaned
    assert "STAR" not in cleaned
    assert "请随时" not in cleaned
    assert cleaned.endswith("[1] 简历正文")


def test_strip_promotional_tail_keeps_normal_report() -> None:
    report = "## 结论\n\n这是正常报告内容。\n\n## 参考来源\n\n[1] 来源"

    cleaned = _strip_promotional_tail(report)

    assert cleaned == report


def test_strip_invalid_citations_removes_out_of_range() -> None:
    from app.services.llm import _strip_invalid_citations

    text = "混合检索 [1][3][5] 与切块 [2][99] 相关"
    cleaned = _strip_invalid_citations(text, max_citation=4)

    assert cleaned == "混合检索 [1][3] 与切块 [2] 相关"


def test_strip_invalid_citations_keeps_valid_only() -> None:
    from app.services.llm import _strip_invalid_citations

    text = "全部有效 [1][2][3]"
    cleaned = _strip_invalid_citations(text, max_citation=3)

    assert cleaned == text


def test_generate_report_strips_invalid_citations(
        monkeypatch,
) -> None:
    from app.services.llm import generate_report

    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock(
        return_value=build_ai_message(
            "结论 [1][5] 有效引用",
            input_tokens=10,
            output_tokens=5,
        )
    )
    monkeypatch.setattr(
        "app.services.llm.get_llm",
        lambda: mock_llm,
    )

    answer = asyncio.run(
        generate_report(
            "问题",
            "[1] 资料A\n[2] 资料B",
            max_citation=2,
        )
    )

    assert answer == "结论 [1] 有效引用"


def test_strip_invalid_citations_truncates_range() -> None:
    from app.services.llm import _strip_invalid_citations

    text = "核心结论：RAG 的核心技术支柱（基于 [1]–[5]）"
    cleaned = _strip_invalid_citations(text, max_citation=4)

    assert cleaned == "核心结论：RAG 的核心技术支柱（基于 [1]-[4]）"


def test_strip_invalid_citations_removes_trailing_range() -> None:
    from app.services.llm import _strip_invalid_citations

    text = "核心结论：RAG 的核心技术支柱（基于 [1]–）"
    cleaned = _strip_invalid_citations(text, max_citation=4)

    assert cleaned == "核心结论：RAG 的核心技术支柱"


def test_strip_invalid_citations_keeps_valid_range() -> None:
    from app.services.llm import _strip_invalid_citations

    text = "（基于 [1]-[3]）"
    cleaned = _strip_invalid_citations(text, max_citation=4)

    assert cleaned == text
