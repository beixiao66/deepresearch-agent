from fastapi import APIRouter

from app.schemas.research import ResearchPlan, ResearchPlanRequest
from app.services.planner import generate_research_plan

router = APIRouter(prefix="/research",tags=["research"])

@router.post("/plan",response_model=ResearchPlan)
async def create_research_plan(request: ResearchPlanRequest) -> ResearchPlan:
    return await generate_research_plan(request.topic)

