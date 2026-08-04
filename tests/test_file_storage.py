import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from app.services.file_storage import FileStorageService


def build_settings(
        upload_directory: str,
        max_upload_size: int = 10,
        upload_chunk_size: int = 4,
) -> Settings:
    return Settings(
        upload_directory=upload_directory,
        max_upload_size=max_upload_size,
        upload_chunk_size=upload_chunk_size,
    )


def build_upload(
        filename: str,
        content: bytes,
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
    )


def test_file_storage_saves_supported_document(
        tmp_path,
) -> None:
    async def run_test() -> None:
        service = FileStorageService(
            build_settings(
                upload_directory=str(tmp_path),
            )
        )
        upload = build_upload(
            filename="../../RAG.PDF",
            content=b"12345678",
        )

        stored = await service.save(
            knowledge_base_id=10,
            upload=upload,
        )

        stored_path = Path(stored.storage_path)

        assert stored.original_filename == "RAG.PDF"
        assert stored.file_extension == ".pdf"
        assert stored.file_size == 8
        assert stored_path.parent == (
                tmp_path / "10"
        ).resolve()
        assert stored_path.suffix == ".pdf"
        assert stored_path.name != "RAG.PDF"
        assert stored_path.read_bytes() == b"12345678"

    asyncio.run(run_test())


def test_file_storage_rejects_unsupported_type(
        tmp_path,
) -> None:
    async def run_test() -> None:
        service = FileStorageService(
            build_settings(str(tmp_path))
        )

        with pytest.raises(
                UnsupportedDocumentTypeError
        ):
            await service.save(
                knowledge_base_id=1,
                upload=build_upload(
                    "malware.exe",
                    b"content",
                ),
            )

        assert list(tmp_path.rglob("*")) == []

    asyncio.run(run_test())


def test_file_storage_rejects_empty_document(
        tmp_path,
) -> None:
    async def run_test() -> None:
        service = FileStorageService(
            build_settings(str(tmp_path))
        )

        with pytest.raises(EmptyDocumentError):
            await service.save(
                knowledge_base_id=1,
                upload=build_upload(
                    "empty.txt",
                    b"",
                ),
            )

        assert not list(tmp_path.rglob("*.txt"))

    asyncio.run(run_test())


def test_file_storage_removes_oversized_document(
        tmp_path,
) -> None:
    async def run_test() -> None:
        service = FileStorageService(
            build_settings(
                upload_directory=str(tmp_path),
                max_upload_size=5,
                upload_chunk_size=4,
            )
        )

        with pytest.raises(DocumentTooLargeError):
            await service.save(
                knowledge_base_id=1,
                upload=build_upload(
                    "large.md",
                    b"12345678",
                ),
            )

        assert not list(tmp_path.rglob("*.md"))

    asyncio.run(run_test())