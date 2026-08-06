from fastapi import APIRouter

from app.schemas.research import ResearchPlan, ResearchPlanRequest
from app.schemas.research_report import ResearchReport, ResearchRequest
from app.services.planner import generate_research_plan
from app.services.research import run_research

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/plan", response_model=ResearchPlan)
async def create_research_plan(
        request: ResearchPlanRequest,
) -> ResearchPlan:
    return await generate_research_plan(request.topic)


@router.post("", response_model=ResearchReport)
async def create_research(
        request: ResearchRequest,
) -> ResearchReport:
    return await run_research(request)
