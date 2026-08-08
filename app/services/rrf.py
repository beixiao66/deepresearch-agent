"""RRF（Reciprocal Rank Fusion）：融合多路检索结果的排名。

核心思想：不看分数（两路分数量纲不同不可比），只看排名。
分数 = Σ 1 / (k + rank)，k 为经验常数（默认 60）。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FusionItem:
    document_id: int | None
    chunk_index: int | None
    text: str
    score: float


K_CONSTANT = 60


def rrf_fuse(
        ranked_lists: list[list[tuple[int | None, int | None, str]]],
        limit: int = 10,
) -> list[FusionItem]:
    """融合多路（文档_id, 块索引, 文本）排名列表。

    ranked_lists: 每路按相关度降序排列的 (document_id, chunk_index, text) 列表。
    """
    scores: dict[tuple[int | None, int | None], float] = {}
    texts: dict[tuple[int | None, int | None], str] = {}

    for ranked_list in ranked_lists:
        for rank, (document_id, chunk_index, text) in enumerate(
                ranked_list,
                start=1,
        ):
            key = (document_id, chunk_index)
            scores[key] = scores.get(key, 0.0) + 1.0 / (
                K_CONSTANT + rank
            )
            texts[key] = text

    fused = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        FusionItem(
            document_id=key[0],
            chunk_index=key[1],
            text=texts[key],
            score=score,
        )
        for key, score in fused[:limit]
    ]
