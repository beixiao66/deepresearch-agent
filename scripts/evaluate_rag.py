"""RAG 离线评估脚本：Recall@K 与 MRR。

用法（项目根目录执行）：
    python scripts/evaluate_rag.py

前置条件：
    1. Qdrant 容器已启动
    2. 知识库 3（RAG评估语料库）已灌入 18/19/22 章文档
    3. .env 已配置 DASHSCOPE_API_KEY

金标标注：每个问题标注"相关文档 ID 列表"（文档级）。
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.services.document_retriever import DocumentRetriever
from app.services.document_embedder import (
    DocumentEmbedder,
    get_embedding_client,
)
from app.services.qdrant_store import (
    QdrantStore,
    get_qdrant_client,
)
from app.core.config import get_settings

# 文档 ID 对照（RAG评估语料库 knowledge_base_id=3）
#   doc 3 = 18章 向量数据库与Embedding实战
#   doc 4 = 19章 RAG检索增强生成
#   doc 5 = 22章 LangGraph概述与快速入门
DOC_18, DOC_19, DOC_22 = 3, 4, 5

# 评估数据集：问题 + 相关文档 ID（文档级金标）
EVALUATION_SET = [
    # ===== 18章：向量数据库与Embedding =====
    {
        "question": "什么是向量化？",
        "relevant": [DOC_18],
    },
    {
        "question": "向量维度的含义是什么？",
        "relevant": [DOC_18],
    },
    {
        "question": "语义相近与向量相近有什么关系？",
        "relevant": [DOC_18],
    },
    {
        "question": "向量数据库与传统数据库有什么区别？",
        "relevant": [DOC_18],
    },
    {
        "question": "稠密向量和稀疏向量有什么区别？",
        "relevant": [DOC_18],
    },
    {
        "question": "为什么检索常用余弦相似度？",
        "relevant": [DOC_18],
    },
    {
        "question": "精确检索和近似检索有什么区别？",
        "relevant": [DOC_18],
    },
    {
        "question": "常见的向量数据库有哪些？",
        "relevant": [DOC_18],
    },
    {
        "question": "RAG 与向量数据库是什么关系？",
        "relevant": [DOC_18],
    },
    {
        "question": "Embedding 文本向量化的实践规则有哪些？",
        "relevant": [DOC_18],
    },
    # ===== 19章：RAG =====
    {
        "question": "RAG 的定义是什么？",
        "relevant": [DOC_19],
    },
    {
        "question": "RAG 有什么作用？",
        "relevant": [DOC_19],
    },
    {
        "question": "RAG 的索引阶段做了什么？",
        "relevant": [DOC_19],
    },
    {
        "question": "RAG 的检索与生成阶段是如何工作的？",
        "relevant": [DOC_19],
    },
    {
        "question": "管道式 RAG 与 Agent 式 RAG 有什么区别？",
        "relevant": [DOC_19],
    },
    {
        "question": "文档加载器（Document Loaders）是干什么的？",
        "relevant": [DOC_19],
    },
    {
        "question": "为什么要切块？切块太大或太小有什么问题？",
        "relevant": [DOC_19],
    },
    {
        "question": "文本分割器有哪些常见类型？",
        "relevant": [DOC_19],
    },
    {
        "question": "from_documents 和 add_texts 有什么区别？",
        "relevant": [DOC_19],
    },
    {
        "question": "智能运维助手案例是如何使用 RAG 的？",
        "relevant": [DOC_19],
    },
    # ===== 22章：LangGraph =====
    {
        "question": "LangGraph 是什么？",
        "relevant": [DOC_22],
    },
    {
        "question": "为什么需要 LangGraph？它解决了什么问题？",
        "relevant": [DOC_22],
    },
    {
        "question": "LangGraph 的四个核心概念是什么？",
        "relevant": [DOC_22],
    },
    {
        "question": "LangGraph 有哪些使用场景？",
        "relevant": [DOC_22],
    },
    {
        "question": "Graph 的最小构建流程是怎样的？",
        "relevant": [DOC_22],
    },
    {
        "question": "如何在 LangGraph 中做并行检索与汇总回答？",
        "relevant": [DOC_22],
    },
]


def get_retriever() -> DocumentRetriever:
    settings = get_settings()

    return DocumentRetriever(
        embedder=DocumentEmbedder(get_embedding_client()),
        qdrant_store=QdrantStore(
            client=get_qdrant_client(),
            collection_name=settings.qdrant_collection,
            vector_size=1024,
        ),
    )


def compute_metrics(
        results: list,
        relevant_document_ids: list[int],
        k: int,
) -> dict:
    """计算单条问题的 Recall@K 与 MRR。

    results 来自 retriever.retrieve()，按相似度降序排列。
    金标是文档级：一个相关文档命中任意片段即算命中该文档。
    """
    relevant_ids_set = set(relevant_document_ids)

    # 去重：一个文档可能命中多个片段，只计一次
    retrieved_relevant_documents = {
        result.document_id
        for result in results[:k]
        if result.document_id in relevant_ids_set
    }
    recall = (
        len(retrieved_relevant_documents)
        / len(relevant_ids_set)
    )

    # MRR：第一个相关文档的片段在完整结果列表中的排名倒数
    mrr = 0.0
    seen_documents: set[int] = set()
    for rank, result in enumerate(results, start=1):
        if (
            result.document_id in relevant_ids_set
            and result.document_id not in seen_documents
        ):
            mrr = 1.0 / rank
            break
        seen_documents.add(result.document_id)

    return {
        "recall": recall,
        "mrr": mrr,
    }


async def main() -> None:
    settings = get_settings()
    retriever = get_retriever()

    k_values = [5, 10]
    total = len(EVALUATION_SET)
    recalls = {k: 0.0 for k in k_values}
    mrrs = {k: 0.0 for k in k_values}

    print(f"评估知识库: knowledge_base_id={settings.qdrant_collection}")
    print(f"评估问题数: {total}")
    print("=" * 60)

    for index, item in enumerate(EVALUATION_SET, start=1):
        question = item["question"]
        relevant = item["relevant"]

        results = await retriever.retrieve(
            question=question,
            knowledge_base_id=3,
            limit=10,
        )

        top_ids = [
            (result.document_id, round(result.score, 3))
            for result in results[:5]
        ]

        per_k = {
            k: compute_metrics(results, relevant, k)
            for k in k_values
        }
        for k in k_values:
            recalls[k] += per_k[k]["recall"]
            mrrs[k] += per_k[k]["mrr"]

        # 命中情况：检索结果中是否出现相关文档
        relevant_hit = "✓" if any(
            r.document_id in relevant
            for r in results
        ) else "✗"

        print(
            f"[{index:02d}/{total}] {relevant_hit} {question[:40]}"
        )
        print(
            f"        top5={top_ids}"
        )
        print(
            f"        Recall@5={per_k[5]['recall']:.2f} "
            f"Recall@10={per_k[10]['recall']:.2f} "
            f"MRR={per_k[5]['mrr']:.3f}"
        )

    print("=" * 60)
    print("汇总指标：")
    for k in k_values:
        print(
            f"  Recall@{k}: {recalls[k] / total:.3f}"
        )
        print(
            f"  MRR@{k}:   {mrrs[k] / total:.3f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
