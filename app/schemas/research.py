from pydantic import BaseModel, Field, field_validator


class ResearchPlanRequest(BaseModel):
    topic: str = Field(
        min_length=1,
        max_length=500,
        description="用户提交的研究主题",
    )

    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("topic cannot be empty")

        return value


class ResearchPlan(BaseModel):
    topic: str = Field(description="用户提交的研究主题")
    objective: str = Field(description="本次研究的总体目标")
    sub_questions: list[str] = Field(
        min_length=1,
        max_length=5,
        description="需要分别研究的子问题，最多5个",
    )
    search_queries: list[str] = Field(
        min_length=1,
        max_length=10,
        description="用于互联网或知识库检索的关键词，最多10个",
    )

    @field_validator("topic", "objective")
    @classmethod
    def strip_text_fields(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("text field cannot be empty")
        return cleaned_value

    @field_validator("sub_questions", "search_queries")
    @classmethod
    def normalize_text_items(cls, values: list[str]) -> list[str]:
        cleaned_values = [
            value.strip()
            for value in values
            if value.strip()
        ]
        if not cleaned_values:
            raise ValueError("list must contain at least one non-blank item")
        return cleaned_values