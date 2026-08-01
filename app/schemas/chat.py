from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("question cannot be empty")
        return value


class ChatResponse(BaseModel):
    answer: str
    model: str
