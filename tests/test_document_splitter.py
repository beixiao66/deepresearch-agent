from app.services.document_splitter import DocumentSplitter


def test_split_long_text_into_multiple_chunks() -> None:
    text = "这是一段用于测试切分的中文文本。" * 100

    splitter = DocumentSplitter(
        chunk_size=100,
        chunk_overlap=20,
    )

    chunks = splitter.split(text)

    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert all(chunk.text for chunk in chunks)


def test_split_short_text_into_single_chunk() -> None:
    text = "短文本"

    splitter = DocumentSplitter()

    chunks = splitter.split(text)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "短文本"


def test_split_chunks_have_expected_overlap() -> None:
    text = "A" * 300

    splitter = DocumentSplitter(
        chunk_size=100,
        chunk_overlap=20,
    )

    chunks = splitter.split(text)

    assert len(chunks) == 4
    assert chunks[0].text[-20:] == chunks[1].text[:20]