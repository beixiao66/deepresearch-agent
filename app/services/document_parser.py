from dataclasses import dataclass

import logging
from pathlib import Path

from pypdf import PdfReader

from app.services.file_storage import ALLOWED_DOCUMENT_EXTENSIONS


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    page_count: int | None = None


logger = logging.getLogger(__name__)


class DocumentParser:
    def parse(
            self,
            storage_path: str,
            file_extension: str,
    ) -> ParsedDocument:
        file_path = Path(storage_path)

        if file_extension == ".txt":
            return self._parse_text(file_path)
        if file_extension == ".md":
            return self._parse_text(file_path)
        if file_extension == ".pdf":
            return self._parse_pdf(file_path)

        raise ValueError(
            f"Unsupported document extension: {file_extension}"
        )

    @staticmethod
    def _parse_text(file_path: Path) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8")
        return ParsedDocument(text=text)

    @staticmethod
    def _parse_pdf(file_path: Path) -> ParsedDocument:
        reader = PdfReader(str(file_path))

        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")

        text = "\n".join(pages).strip()

        return ParsedDocument(
            text=text,
            page_count=len(reader.pages),
        )