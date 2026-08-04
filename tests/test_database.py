from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.document import DocumentRepository
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event

from app import models
from app.db.base import Base
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document, DocumentStatus


def enable_sqlite_foreign_keys(test_engine) -> None:
    @event.listens_for(test_engine.sync_engine, "connect")
    def enable_foreign_keys(
            dbapi_connection,
            _connection_record,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def test_create_and_query_knowledge_base(tmp_path) -> None:
    async def run_test() -> None:
        database_path = tmp_path / "test.db"
        database_url = (
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )

        test_engine = create_async_engine(database_url)
        enable_sqlite_foreign_keys(test_engine)
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
        enable_sqlite_foreign_keys(test_engine)
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


def test_delete_knowledge_base_cascades_documents(
        tmp_path,
) -> None:
    async def run_test() -> None:
        database_path = tmp_path / "cascade.db"
        database_url = (
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )

        test_engine = create_async_engine(database_url)
        enable_sqlite_foreign_keys(test_engine)
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
                    name="RAG 资料库",
                    description="测试级联删除",
                )
                session.add(knowledge_base)
                await session.flush()

                document = Document(
                    knowledge_base_id=knowledge_base.id,
                    original_filename="rag.md",
                    storage_path="data/uploads/test-rag.md",
                    file_extension=".md",
                    file_size=100,
                    mime_type="text/markdown",
                    status=DocumentStatus.PENDING.value,
                )
                session.add(document)
                await session.commit()

                knowledge_base_id = knowledge_base.id
                document_id = document.id

            async with test_session_factory() as session:
                stored_document = await session.get(
                    Document,
                    document_id,
                )
                assert stored_document is not None

                stored_knowledge_base = await session.get(
                    KnowledgeBase,
                    knowledge_base_id,
                )
                assert stored_knowledge_base is not None

                await session.delete(stored_knowledge_base)
                await session.commit()

            async with test_session_factory() as session:
                deleted_document = await session.get(
                    Document,
                    document_id,
                )
                assert deleted_document is None
        finally:
            await test_engine.dispose()

    asyncio.run(run_test())


def test_document_repository_create_list_and_get(
        tmp_path,
) -> None:
    async def run_test() -> None:
        database_path = tmp_path / "documents.db"
        database_url = (
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )

        test_engine = create_async_engine(database_url)
        enable_sqlite_foreign_keys(test_engine)

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
                    description=None,
                )
                session.add(knowledge_base)
                await session.flush()

                repository = DocumentRepository(session)

                first = await repository.create(
                    knowledge_base_id=knowledge_base.id,
                    original_filename="rag.pdf",
                    storage_path="data/uploads/rag.pdf",
                    file_extension=".pdf",
                    file_size=2048,
                    mime_type="application/pdf",
                )
                second = await repository.create(
                    knowledge_base_id=knowledge_base.id,
                    original_filename="agent.md",
                    storage_path="data/uploads/agent.md",
                    file_extension=".md",
                    file_size=1024,
                    mime_type="text/markdown",
                )

                await session.commit()

                knowledge_base_id = knowledge_base.id
                first_id = first.id
                second_id = second.id

            async with test_session_factory() as session:
                repository = DocumentRepository(session)

                stored = await repository.get_by_id(
                    knowledge_base_id,
                    first_id,
                )
                documents = (
                    await repository.list_by_knowledge_base(
                        knowledge_base_id
                    )
                )

                assert stored is not None
                assert stored.original_filename == "rag.pdf"
                assert stored.status == "pending"

                assert [
                           document.id
                           for document in documents
                       ] == [second_id, first_id]

                wrong_knowledge_base = await repository.get_by_id(
                    knowledge_base_id + 999,
                    first_id,
                )
                assert wrong_knowledge_base is None
        finally:
            await test_engine.dispose()

    asyncio.run(run_test())