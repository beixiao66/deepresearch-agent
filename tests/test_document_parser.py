from pathlib import Path

from app.services.document_parser import DocumentParser


def test_parse_txt_document(tmp_path) -> None:
    document_path = tmp_path / "notes.txt"
    document_path.write_text(
        "第一条笔记\n第二条笔记",
        encoding="utf-8",
    )

    parser = DocumentParser()
    parsed = parser.parse(
        str(document_path),
        ".txt",
    )

    assert "第一条笔记" in parsed.text
    assert "第二条笔记" in parsed.text
    assert parsed.page_count is None


def test_parse_markdown_document(tmp_path) -> None:
    document_path = tmp_path / "notes.md"
    document_path.write_text(
        "# 标题\n\n正文内容",
        encoding="utf-8",
    )

    parser = DocumentParser()
    parsed = parser.parse(
        str(document_path),
        ".md",
    )

    assert "# 标题" in parsed.text
    assert "正文内容" in parsed.text


def test_parse_pdf_document(tmp_path) -> None:
    # 使用 pypdf 生成一个简单 PDF
    from pypdf import PdfWriter

    pdf_path = tmp_path / "test.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)

    with pdf_path.open("wb") as file:
        writer.write(file)

    parser = DocumentParser()
    parsed = parser.parse(
        str(pdf_path),
        ".pdf",
    )

    assert parsed.page_count == 1
    assert isinstance(parsed.text, str)


def test_parse_unsupported_extension(tmp_path) -> None:
    document_path = tmp_path / "notes.exe"
    document_path.write_text("content", encoding="utf-8")

    parser = DocumentParser()

    import pytest

    with pytest.raises(ValueError):
        parser.parse(
            str(document_path),
            ".exe",
        )


def test_parse_text_document_with_bom(tmp_path) -> None:
    """记事本「UTF-8 带 BOM」另存的 txt/md，首行不应残留 \\ufeff。"""
    for extension in (".txt", ".md"):
        document_path = tmp_path / f"bom{extension}"
        document_path.write_text(
            "第一行内容\n第二行内容",
            encoding="utf-8-sig",
        )

        parsed = DocumentParser().parse(
            str(document_path),
            extension,
        )

        assert "\ufeff" not in parsed.text
        assert parsed.text.startswith("第一行内容")