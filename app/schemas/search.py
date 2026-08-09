from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
    )

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError(
                    "question cannot be empty"
                )

        return value


class SearchResultItem(BaseModel):
    document_id: int | None
    chunk_index: int | None
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]