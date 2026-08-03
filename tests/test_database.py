from app.repositories.knowledge_base import KnowledgeBaseRepository
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.models.knowledge_base import KnowledgeBase


def test_create_and_query_knowledge_base(tmp_path) -> None:
    async def run_test() -> None:
        database_path = tmp_path / "test.db"
        database_url = (
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )

        test_engine = create_async_engine(database_url)
        test_session_factory = async_sessionmaker(
            bind=test_engine,
            expire_on_commit=False,
        )

        try:
            async with test_engine.begin() as connection:
                await connection.run_sync(
                    Base.metadata.create_all
                )

            async with test_session_factory() as session:
                knowledge_base = KnowledgeBase(
                    name="AI 技术资料库",
                    description="保存 RAG 与 Agent 技术资料",
                )

                session.add(knowledge_base)
                await session.commit()

                knowledge_base_id = knowledge_base.id

            async with test_session_factory() as session:
                statement = select(KnowledgeBase).where(
                    KnowledgeBase.id == knowledge_base_id
                )
                result = await session.execute(statement)
                stored_knowledge_base = result.scalar_one()

                assert stored_knowledge_base.id == knowledge_base_id
                assert stored_knowledge_base.name == "AI 技术资料库"
                assert (
                        stored_knowledge_base.description
                        == "保存 RAG 与 Agent 技术资料"
                )
                assert stored_knowledge_base.created_at is not None
                assert stored_knowledge_base.updated_at is not None
        finally:
            await test_engine.dispose()

    asyncio.run(run_test())


def test_knowledge_base_repository_create_get_and_list(
        tmp_path,
) -> None:
    async def run_test() -> None:
        database_path = tmp_path / "repository.db"
        database_url = (
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )

        test_engine = create_async_engine(database_url)
        test_session_factory = async_sessionmaker(
            bind=test_engine,
            expire_on_commit=False,
        )

        try:
            async with test_engine.begin() as connection:
                await connection.run_sync(
                    Base.metadata.create_all
                )

            async with test_session_factory() as session:
                repository = KnowledgeBaseRepository(session)

                first = await repository.create(
                    name="RAG 资料库",
                    description="RAG 技术资料",
                )
                second = await repository.create(
                    name="Agent 资料库",
                    description=None,
                )

                await session.commit()

                first_id = first.id
                second_id = second.id

            async with test_session_factory() as session:
                repository = KnowledgeBaseRepository(session)

                stored = await repository.get_by_id(first_id)
                knowledge_bases = await repository.list_all()

                assert stored is not None
                assert stored.name == "RAG 资料库"
                assert stored.description == "RAG 技术资料"

                assert [
                           knowledge_base.id
                           for knowledge_base in knowledge_bases
                       ] == [second_id, first_id]
        finally:
            await test_engine.dispose()

    asyncio.run(run_test())