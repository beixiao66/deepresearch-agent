"""chat 微型 LangGraph 图：多轮对话记忆（thread 内）。

复用 research_graph.get_checkpointer（AsyncSqliteSaver 单例），
thread_id = "chat-{conversation_id}"。消息总量超过 TOKEN_BOUNDARY
时，把最老的 KEEP_RAW 条之外的消息压缩成一段摘要存入 summary
通道并删除原文，实现"老摘要 + 新原文"的恒定窗口。
"""
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langgraph.graph import END, START, StateGraph, add_messages

from app.services.llm import CHAT_SYSTEM_PROMPT, get_llm
from app.services.research_graph import get_checkpointer

# 摘要阈值：qwen-plus 窗口 128K，取 1/8 留足余量（实现时可调）
TOKEN_BOUNDARY = 16000
# 摘要时保留的最近原文条数，其余老消息压缩进 summary
KEEP_RAW = 10


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    summary: str


def _estimate_tokens(*texts: str) -> int:
    """估算 token 数：优先 tiktoken，不可用时按中文字符粗算。"""
    try:
        from tiktoken import get_encoding

        encoding = get_encoding("cl100k_base")
        return sum(len(encoding.encode(text)) for text in texts)
    except Exception:
        # 中文约 1.5 字符/token 的粗算兜底
        return sum(len(text) * 2 // 3 for text in texts)


async def _chat_node(state: ChatState) -> dict:
    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)]
    if state.get("summary"):
        messages.append(SystemMessage(
            content=f"以下是更早对话的摘要，供回答时参考：\n{state['summary']}"
        ))
    messages.extend(state["messages"])

    response = await get_llm().ainvoke(messages)
    return {"messages": [AIMessage(content=str(response.content))]}


async def _summarize_node(state: ChatState) -> dict:
    """摘要节点：总 token 超阈值时压缩老消息为摘要并删除原文。

    触发后 messages 通道只保留最近 KEEP_RAW 条原文，其余进 summary；
    摘要覆盖写入 summary 通道，保证上下文窗口恒定。
    """
    summary = state.get("summary", "")
    messages = state["messages"]
    total_tokens = _estimate_tokens(
        summary,
        *(str(m.content) for m in messages),
    )
    if total_tokens <= TOKEN_BOUNDARY:
        return {}

    old_messages = messages[:-KEEP_RAW]
    if not old_messages:
        return {}

    prompt = []
    if summary:
        prompt.append(SystemMessage(content=f"已有对话摘要：\n{summary}"))
    prompt.extend(old_messages)

    result = await get_llm().ainvoke(prompt)
    removes = [
        RemoveMessage(id=m.id)
        for m in old_messages
        if m.id is not None
    ]
    return {
        "summary": str(result.content),
        "messages": removes,
    }


async def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("chat", _chat_node)
    graph.add_node("summarize", _summarize_node)
    graph.add_edge(START, "summarize")
    graph.add_edge("summarize", "chat")
    graph.add_edge("chat", END)

    checkpointer = await get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


_chat_graph = None


async def get_chat_graph():
    global _chat_graph
    if _chat_graph is None:
        _chat_graph = await build_chat_graph()
    return _chat_graph
