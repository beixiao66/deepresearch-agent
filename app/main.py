from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.api.routes.research import router as research_router
from app.api.routes.knowledge_base import router as knowledge_base_router
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()

    yield

    await engine.dispose()


configure_logging()

app = FastAPI(
    title="DeepResearch Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")
app.include_router(knowledge_base_router,prefix="/api/v1",)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}