from pydantic import BaseModel, Field, field_validator

from app.schemas.research import ResearchPlan


class ResearchRequest(BaseModel):
    topic: str = Field(
        min_length=1,
        max_length=500,
        description="用户提交的研究主题",
    )
    knowledge_base_id: int = Field(
        default=1,
        gt=0,
        description="要检索的知识库 ID",
    )
    use_web_search: bool = Field(
        default=False,
        description="知识库不足时是否允许联网搜索",
    )

    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("topic cannot be empty")

        return value


class SourceItem(BaseModel):
    document_id: int | None = None
    chunk_index: int | None = None
    text: str
    score: float
    query: str
    source_type: str = "kb"
    url: str | None = None


class ResearchReport(BaseModel):
    topic: str
    plan: ResearchPlan
    sources: list[SourceItem]
    answer: str
    task_id: int | None = None


class ResearchTaskResponse(BaseModel):
    id: int
    topic: str
    knowledge_base_id: int
    status: str
    plan: str | None = None
    report: str | None = None
    error_message: str | None = None
    token_usage: str | None = None

    model_config = {"from_attributes": True}


class ApproveRequest(BaseModel):
    approved: bool
