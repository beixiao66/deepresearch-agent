from pathlib import Path

from sqlalchemy import text

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

        # 轻量迁移：token_usage 列不存在时才添加（幂等）
        result = await connection.execute(
            text("PRAGMA table_info(research_tasks)")
        )
        columns = {row[1] for row in result.all()}

        if "token_usage" not in columns:
            await connection.execute(
                text(
                    "ALTER TABLE research_tasks "
                    "ADD COLUMN token_usage TEXT"
                )
            )

        if "sources" not in columns:
            await connection.execute(
                text(
                    "ALTER TABLE research_tasks "
                    "ADD COLUMN sources TEXT"
                )
            )