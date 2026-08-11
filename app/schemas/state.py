from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.schemas.research import ResearchPlan


class ResearchState(TypedDict):
    """LangGraph 图节点间共享的状态。"""
    question: str
    knowledge_base_id: int
    use_web_search: bool
    plan: ResearchPlan
    sources: list[dict]
    answer: str
    retrieval_round: int
    next_queries: list[str]
    token_usage: dict
    messages: Annotated[list[AnyMessage], add_messages]
