from fastapi import APIRouter, Path
from fastapi.responses import StreamingResponse

from app.api.dependencies import (
    ResearchTaskRepositoryDependency,
)
from app.schemas.research import ResearchPlan, ResearchPlanRequest
from app.schemas.research_report import (
    ApproveRequest,
    ResearchRequest,
    ResearchTaskResponse,
)
from app.services.planner import generate_research_plan
from app.services.sse import (
    stream_approve_research,
    stream_start_research,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/plan", response_model=ResearchPlan)
async def create_research_plan(
        request: ResearchPlanRequest,
) -> ResearchPlan:
    return await generate_research_plan(request.topic)


@router.post("")
async def create_research(
        request: ResearchRequest,
        task_repository: ResearchTaskRepositoryDependency,
) -> StreamingResponse:
    return StreamingResponse(
        stream_start_research(request, task_repository),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tasks/{task_id}/approve")
async def approve_research_task(
        task_id: int = Path(gt=0),
        request: ApproveRequest = None,
        task_repository: ResearchTaskRepositoryDependency = None,
) -> StreamingResponse:
    return StreamingResponse(
        stream_approve_research(
            task_id,
            request.approved,
            task_repository,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
