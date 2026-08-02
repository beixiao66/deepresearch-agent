import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accepts_valid_log_level(
        monkeypatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.log_level == "DEBUG"


def test_settings_rejects_invalid_log_level(
        monkeypatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INVALID")

    with pytest.raises(ValidationError):
        Settings()

