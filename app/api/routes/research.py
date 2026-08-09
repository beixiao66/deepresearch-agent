from fastapi import APIRouter, Path

from app.api.dependencies import (
    ResearchTaskRepositoryDependency,
)
from app.schemas.research import ResearchPlan, ResearchPlanRequest
from app.schemas.research_report import (
    ResearchReport,
    ResearchRequest,
    ResearchTaskResponse,
)
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
        task_repository: ResearchTaskRepositoryDependency,
) -> ResearchReport:
    return await run_research(request, task_repository)


@router.get("/tasks", response_model=list[ResearchTaskResponse])
async def list_research_tasks(
        task_repository: ResearchTaskRepositoryDependency,
) -> list[ResearchTaskResponse]:
    tasks = await task_repository.list_all()

    return [
        ResearchTaskResponse.model_validate(task)
        for task in tasks
    ]


@router.get("/tasks/{task_id}", response_model=ResearchTaskResponse)
async def get_research_task(
        task_id: int = Path(gt=0),
        task_repository: ResearchTaskRepositoryDependency = None,
) -> ResearchTaskResponse:
    task = await task_repository.get_by_id(task_id)

    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Research task not found")

    return ResearchTaskResponse.model_validate(task)
