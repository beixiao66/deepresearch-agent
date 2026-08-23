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
    # LangGraph 持久化 checkpointer（AsyncSqliteSaver）的数据库文件，
    # 进程重启后研究任务的执行现场（interrupt 暂停点）仍可恢复
    checkpoint_db_path: str = "data/langgraph_checkpoints.db"
    upload_directory: str = "data/uploads"
    max_upload_size: int = 10 * 1024 * 1024
    upload_chunk_size: int = 1024 * 1024
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "deepresearch_documents"
@lru_cache
def get_settings() -> Settings:
    return Settings()
