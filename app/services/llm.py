from functools import lru_cache

from langchain_openai import ChatOpenAI
from app.core.config import get_settings


@lru_cache
def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.dashscope_api_key,
        base_url = settings.dashscope_base_url,
        model=settings.llm_model,
        temperature=0,
        timeout=30,
        max_retries=2,
    )