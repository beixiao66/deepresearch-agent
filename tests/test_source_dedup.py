from app.services.source_dedup import (
    dedupe_sources,
    select_top_per_sub_question,
)


def test_dedupe_kb_sources_keeps_highest_score() -> None:
    sources = [
        {
            "source_type": "kb",
            "document_id": 1,
            "chunk_index": 2,
            "text": "相同片段",
            "score": 0.5,
        },
        {
            "source_type": "kb",
            "document_id": 1,
            "chunk_index": 2,
            "text": "相同片段",
            "score": 0.8,
        },
        {
            "source_type": "kb",
            "document_id": 1,
            "chunk_index": 3,
            "text": "不同片段",
            "score": 0.6,
        },
    ]

    result = dedupe_sources(sources)

    assert len(result) == 2
    # 相同片段保留最高分 0.8
    assert result[0]["score"] == 0.8
    assert result[0]["chunk_index"] == 2
    assert result[1]["chunk_index"] == 3


def test_dedupe_web_sources_by_url() -> None:
    sources = [
        {
            "source_type": "web",
            "url": "https://example.com/a",
            "text": "网页A",
            "score": 0.4,
        },
        {
            "source_type": "web",
            "url": "https://example.com/a",
            "text": "网页A",
            "score": 0.7,
        },
        {
            "source_type": "web",
            "url": "https://example.com/b",
            "text": "网页B",
            "score": 0.5,
        },
    ]

    result = dedupe_sources(sources)

    assert len(result) == 2
    assert result[0]["url"] == "https://example.com/a"
    assert result[0]["score"] == 0.7
    assert result[1]["url"] == "https://example.com/b"


def test_dedupe_preserves_first_seen_order() -> None:
    sources = [
        {
            "source_type": "kb",
            "document_id": 3,
            "chunk_index": 0,
            "text": "片段A",
            "score": 0.5,
        },
        {
            "source_type": "kb",
            "document_id": 1,
            "chunk_index": 0,
            "text": "片段B",
            "score": 0.9,
        },
        {
            "source_type": "kb",
            "document_id": 3,
            "chunk_index": 0,
            "text": "片段A",
            "score": 0.6,
        },
    ]

    result = dedupe_sources(sources)

    assert [s["document_id"] for s in result] == [3, 1]
    # 首次出现的片段 3 被后续更高分更新
    assert result[0]["score"] == 0.6


def test_select_top_per_sub_question_limits_each_sub_question() -> None:
    sub_answers = [
        {
            "question": "子问题1",
            "sources": [
                {"document_id": 1, "chunk_index": i, "text": f"a{i}", "score": i / 10}
                for i in range(8)
            ],
        },
        {
            "question": "子问题2",
            "sources": [
                {"document_id": 2, "chunk_index": i, "text": f"b{i}", "score": i / 10}
                for i in range(8)
            ],
        },
    ]

    result = select_top_per_sub_question(sub_answers, top_k=5)

    assert len(result) == 10
    sub1 = [s for s in result if s["document_id"] == 1]
    assert [s["chunk_index"] for s in sub1] == [7, 6, 5, 4, 3]


def test_select_top_per_sub_question_dedupes_across_sub_questions() -> None:
    sub_answers = [
        {
            "question": "子问题1",
            "sources": [
                {"document_id": 1, "chunk_index": 0, "text": "相同", "score": 0.5},
            ],
        },
        {
            "question": "子问题2",
            "sources": [
                {"document_id": 1, "chunk_index": 0, "text": "相同", "score": 0.9},
            ],
        },
    ]

    result = select_top_per_sub_question(sub_answers, top_k=5)

    assert len(result) == 1
    assert result[0]["score"] == 0.9
