from pathlib import Path

from app import models
from app.db.base import Base
from app.db.session import engine

DATABASE_DIRECTORY = Path("data")


async def init_db() -> None:
    DATABASE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )