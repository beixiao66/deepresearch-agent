from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.api.routes.research import router as research_router
from app.core.logging import configure_logging
from app.core.exceptions import register_exception_handlers

configure_logging()
app = FastAPI(
    title="DeepResearch Agent API",
    version="0.1.0",
)

register_exception_handlers(app)
app.include_router(chat_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}