from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    dashscope_api_key: SecretStr
    tavily_api_key: SecretStr
    dashscope_base_url: str
    llm_model: str
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/deepresearch.db"
    upload_directory: str = "data/uploads"
    max_upload_size: int = 10 * 1024 * 1024
    upload_chunk_size: int = 1024 * 1024

@lru_cache
def get_settings() -> Settings:
    return Settings()
