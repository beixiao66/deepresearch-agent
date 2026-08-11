import logging

from app.schemas.research import ResearchPlan
from app.services.llm import generate_research_plan as _generate_plan

logger = logging.getLogger(__name__)


async def generate_research_plan(
        topic: str,
        usage_counters: dict | None = None,
) -> ResearchPlan:
    """生成研究计划（委托给 llm.py，保证 token 用量被记录）。"""
    plan = await _generate_plan(topic, usage_counters)

    logger.info(
        "Research plan generated: sub_questions=%d, search_queries=%d",
        len(plan.sub_questions),
        len(plan.search_queries),
    )

    return plan
