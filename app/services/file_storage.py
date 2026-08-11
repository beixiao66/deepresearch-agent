from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import (
      DocumentTooLargeError,
      EmptyDocumentError,
      UnsupportedDocumentTypeError,
  )

ALLOWED_DOCUMENT_EXTENSIONS = {
      ".pdf",
      ".md",
      ".txt",
      ".docx",
      ".html",
      ".htm",
      ".xlsx",
      ".pptx",
      ".csv",
}


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    storage_path: str
    file_extension: str
    file_size: int
    mime_type: str | None


class FileStorageService:
    def __init__(self, settings: Settings) -> None:
        self.upload_root = Path(
            settings.upload_directory
        ).resolve()
        self.max_upload_size = settings.max_upload_size
        self.upload_chunk_size = settings.upload_chunk_size

    async def save(
            self,
            knowledge_base_id: int,
            upload: UploadFile,
    ) -> StoredFile:
        original_filename = self._get_original_filename(
            upload
        )
        file_extension = Path(
            original_filename
        ).suffix.lower()

        if file_extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise UnsupportedDocumentTypeError(
                file_extension
            )

        target_directory = (
                self.upload_root / str(knowledge_base_id)
        ).resolve()
        self._ensure_path_is_allowed(target_directory)
        target_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        storage_filename = (
            f"{uuid4().hex}{file_extension}"
        )
        target_path = (
                target_directory / storage_filename
        ).resolve()
        self._ensure_path_is_allowed(target_path)

        file_size = 0

        try:
            async with await anyio.open_file(
                    target_path,
                    mode="wb",
            ) as destination:
                while True:
                    chunk = await upload.read(
                        self.upload_chunk_size
                    )

                    if not chunk:
                        break

                    file_size += len(chunk)

                    if file_size > self.max_upload_size:
                        raise DocumentTooLargeError(
                            self.max_upload_size
                        )

                    await destination.write(chunk)

            if file_size == 0:
                raise EmptyDocumentError()
        except Exception:
            await self._remove_file_if_exists(
                target_path
            )
            raise
        finally:
            await upload.close()

        return StoredFile(
            original_filename=original_filename,
            storage_path=str(target_path),
            file_extension=file_extension,
            file_size=file_size,
            mime_type=upload.content_type,
        )

    @staticmethod
    def _get_original_filename(
            upload: UploadFile,
    ) -> str:
        if not upload.filename:
            raise UnsupportedDocumentTypeError("")

        normalized_filename = upload.filename.replace(
            "\\",
            "/",
        )
        original_filename = Path(
            normalized_filename
        ).name.strip()

        if not original_filename:
            raise UnsupportedDocumentTypeError("")

        return original_filename

    def _ensure_path_is_allowed(
            self,
            path: Path,
    ) -> None:
        if not path.is_relative_to(self.upload_root):
            raise ValueError(
                "Storage path escapes upload directory"
            )

    @staticmethod
    async def _remove_file_if_exists(
            path: Path,
    ) -> None:
        if path.exists():
            await anyio.to_thread.run_sync(
                path.unlink
            )

    async def remove(self, storage_path: str) -> None:
        resolved_path = Path(storage_path).resolve()

        self._ensure_path_is_allowed(resolved_path)
        await self._remove_file_if_exists(resolved_path)