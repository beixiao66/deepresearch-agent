"""Tavily 联网搜索：知识库不足时的补充检索路。"""
import logging

from dataclasses import dataclass
from functools import lru_cache

from tavily import TavilyClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    content: str
    score: float


@lru_cache
def get_tavily_client() -> TavilyClient:
    settings = get_settings()

    return TavilyClient(
        api_key=settings.tavily_api_key.get_secret_value()
    )


def search_web(
        query: str,
        max_results: int = 5,
) -> list[WebSearchResult]:
    """调用 Tavily 搜索，返回结果列表（按相关性降序）。"""
    try:
        response = get_tavily_client().search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )

        results = [
            WebSearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
            )
            for item in response.get("results", [])
        ]

        logger.info(
            "web search: query=%s, results=%d",
            query,
            len(results),
        )

        return results

    except Exception as exc:
        logger.error(
            "web search failed: query=%s, error=%s",
            query,
            exc,
            exc_info=True,
        )
        return []
