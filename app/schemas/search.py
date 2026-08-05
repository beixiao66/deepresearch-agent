from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=1000,
    )


class SearchResultItem(BaseModel):
    document_id: int | None
    chunk_index: int | None
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]