# app/api/routes/memory.py
from fastapi import APIRouter

from app.schemas.memory import (
    PreferencesResponse,
    PreferencesUpdate,
)
from app.services.memory_store import (
    get_preferences,
    save_preferences,
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/preferences", response_model=PreferencesResponse)
async def read_preferences(
        user_id: int = 1,
) -> PreferencesResponse:
    return PreferencesResponse(**await get_preferences(user_id))


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
        data: PreferencesUpdate,
) -> PreferencesResponse:
    preferences = {
        "report_style": data.report_style,
        "report_language": data.report_language,
    }
    await save_preferences(data.user_id, preferences)
    return PreferencesResponse(**preferences)
