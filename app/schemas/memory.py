# app/schemas/memory.py
from typing import Literal

from pydantic import BaseModel


class PreferencesUpdate(BaseModel):
    user_id: int = 1
    report_style: Literal["detailed", "concise"] = "detailed"
    report_language: Literal["zh", "en"] = "zh"


class PreferencesResponse(BaseModel):
    report_style: str
    report_language: str
