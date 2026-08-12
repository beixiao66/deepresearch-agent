from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Path, UploadFile
from fastapi.responses import StreamingResponse

from app.api.dependencies import (
    DocumentServiceDependency,
    KnowledgeBaseServiceDependency,
    ResearchTaskRepositoryDependency,
)
from app.core.exceptions import ResearchTaskNotFoundError
from app.schemas.research import ResearchPlan, ResearchPlanRequest
from app.schemas.knowledge_base import KnowledgeBaseCreate
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

# 临时附件知识库名称前缀：创建研究时上传的文件会建立一个临时知识库
TEMP_KB_PREFIX = "研究附件-"


@router.post("/plan", response_model=ResearchPlan)
async def create_research_plan(
        request: ResearchPlanRequest,
) -> ResearchPlan:
    return await generate_research_plan(request.topic)


@router.post("")
async def create_research(
        topic: str = Form(...),
        knowledge_base_id: int | None = Form(default=None),
        use_web_search: bool = Form(default=False),
        file: UploadFile | None = File(default=None),
        task_repository: ResearchTaskRepositoryDependency = None,
        knowledge_base_service: KnowledgeBaseServiceDependency = None,
        document_service: DocumentServiceDependency = None,
) -> StreamingResponse:
    """创建研究任务。

    支持两种模式：
    1. 选择已有知识库：knowledge_base_id 必填
    2. 上传文件：自动创建临时知识库并索引，用该库研究
    """
    topic = topic.strip()
    if not topic:
        raise HTTPException(
            status_code=422,
            detail="topic cannot be empty",
        )

    # 上传文件模式：自动建临时知识库（用完即删，不进知识库列表）
    if file is not None and file.filename:
        kb_name = f"{TEMP_KB_PREFIX}{uuid4().hex[:8]}"
        knowledge_base = await knowledge_base_service.create(
            KnowledgeBaseCreate(
                name=kb_name,
                description="创建研究任务时上传的附件",
            )
        )
        await document_service.upload_document(
            knowledge_base_id=knowledge_base.id,
            upload=file,
        )
        knowledge_base_id = knowledge_base.id

    if knowledge_base_id is None:
        raise HTTPException(
            status_code=422,
            detail="请选择知识库或上传文件",
        )

    request = ResearchRequest(
        topic=topic,
        knowledge_base_id=knowledge_base_id,
        use_web_search=use_web_search,
    )

    return StreamingResponse(
        stream_start_research(
            request,
            task_repository,
            knowledge_base_service=knowledge_base_service,
            temp_kb_prefix=TEMP_KB_PREFIX,
        ),
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
        knowledge_base_service: KnowledgeBaseServiceDependency = None,
) -> StreamingResponse:
    return StreamingResponse(
        stream_approve_research(
            task_id,
            request.approved,
            task_repository,
            knowledge_base_service=knowledge_base_service,
            temp_kb_prefix=TEMP_KB_PREFIX,
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
        raise ResearchTaskNotFoundError(task_id)

    return ResearchTaskResponse.model_validate(task)
