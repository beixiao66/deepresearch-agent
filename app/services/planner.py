from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from app.schemas.research import ResearchPlan
from app.services.llm import get_llm
import logging

logger = logging.getLogger(__name__)

@lru_cache
def get_planner():
    return get_llm().with_structured_output(ResearchPlan)


async def generate_research_plan(topic: str) -> ResearchPlan:
    logger.info("Generating research plan")
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
    plan = await get_planner().ainvoke(messages)

    logger.info(
        "Research plan generated: sub_questions=%d, search_queries=%d",
        len(plan.sub_questions),
        len(plan.search_queries),
    )

    return plan