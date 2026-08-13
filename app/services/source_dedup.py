"""检索来源去重：多 Agent 并行检索时，同一片段可能被多个查询词命中。

去重规则：
- 本地来源（kb）：按 (source_type, document_id, chunk_index) 去重
- 网页来源（web）：按 (source_type, url) 去重
- 保留首次出现顺序，分数取多次命中中的最高分
"""


def dedupe_sources(sources: list[dict]) -> list[dict]:
    """按片段唯一键去重，保留最高相关度。"""
    seen: dict[tuple, dict] = {}
    order: list[tuple] = []

    for source in sources:
        key = _source_key(source)
        if key is None:
            continue

        if key not in seen:
            seen[key] = dict(source)
            order.append(key)
        else:
            # 同一片段多次命中：保留最高分
            if source.get("score", 0.0) > seen[key].get("score", 0.0):
                seen[key] = dict(source)

    return [seen[key] for key in order]


def _source_key(source: dict) -> tuple | None:
    source_type = source.get("source_type", "kb")

    if source_type == "web":
        url = source.get("url")
        if url:
            return ("web", url)
        return None

    document_id = source.get("document_id")
    chunk_index = source.get("chunk_index")
    if document_id is None:
        return None

    return ("kb", document_id, chunk_index)


def select_top_per_sub_question(
        sub_answers: list[dict],
        top_k: int = 5,
) -> list[dict]:
    """每个子问题按相关度取 Top-K 证据，合并后整体去重。

    避免把全部检索证据塞进报告，控制正文引用编号数量。
    """
    selected: list[dict] = []

    for sub_answer in sub_answers:
        sources = sub_answer.get("sources", [])
        ranked = sorted(
            sources,
            key=lambda source: source.get("score", 0.0),
            reverse=True,
        )
        selected.extend(ranked[:top_k])

    return dedupe_sources(selected)
