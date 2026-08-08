"""RAG 离线评估脚本：三档检索对比（纯向量 / 混合 / 混合+Rerank）。

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

from app.db.session import AsyncSessionLocal
from app.services.document_retriever import DocumentRetriever
from app.services.document_embedder import (
    DocumentEmbedder,
    get_embedding_client,
)
from app.services.qdrant_store import (
    QdrantStore,
    get_qdrant_client,
)
from app.services.reranker import get_reranker
from app.services.sparse_indexer import SparseIndexer
from app.services.sparse_retriever import SparseRetriever
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
    # ===== 挑战性问题：跨文档/关键词型，测试混合检索区分度 =====
    # 关键词精确命中（向量可能漏，BM25 稳）
    {
        "question": "Redis Stack 是什么？",
        "relevant": [DOC_18],
    },
    {
        "question": "Milvus 和 Redis 怎么选？",
        "relevant": [DOC_18],
    },
    {
        "question": "DashScope 如何调用 Embedding？",
        "relevant": [DOC_18],
    },
    {
        "question": "LangChain 的 from_documents 是干什么的？",
        "relevant": [DOC_19],
    },
    {
        "question": "RecursiveCharacterTextSplitter 是什么？",
        "relevant": [DOC_19],
    },
    {
        "question": "智能运维助手案例讲了什么？",
        "relevant": [DOC_19],
    },
]


def get_retriever(
        sparse_retriever: SparseRetriever | None = None,
        reranker=None,
) -> DocumentRetriever:
    settings = get_settings()

    return DocumentRetriever(
        embedder=DocumentEmbedder(get_embedding_client()),
        qdrant_store=QdrantStore(
            client=get_qdrant_client(),
            collection_name=settings.qdrant_collection,
            vector_size=1024,
        ),
        sparse_retriever=sparse_retriever,
        reranker=reranker,
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

    async with AsyncSessionLocal() as session:
        await SparseIndexer(session).ensure_table()
        sparse_retriever = SparseRetriever(session)

        retrievers = {
            "dense": get_retriever(),
            "hybrid": get_retriever(
                sparse_retriever=sparse_retriever,
            ),
            "hybrid+rerank": get_retriever(
                sparse_retriever=sparse_retriever,
                reranker=get_reranker(),
            ),
        }

        k_values = [5, 10]
        total = len(EVALUATION_SET)

        # aggregates[检索方式][指标] = 累加值
        aggregates = {
            name: {
                "recall_5": 0.0,
                "recall_10": 0.0,
                "mrr": 0.0,
                "hit": 0,
            }
            for name in retrievers
        }

        print(f"评估知识库: knowledge_base_id=3")
        print(f"评估问题数: {total}，检索方式: {list(retrievers)}")
        print("=" * 90)

        for index, item in enumerate(EVALUATION_SET, start=1):
            question = item["question"]
            relevant = item["relevant"]

            print(f"[{index:02d}/{total}] {question[:36]}")

            for name, retriever in retrievers.items():
                if name == "dense":
                    results = await retriever.retrieve(
                        question=question,
                        knowledge_base_id=3,
                        limit=10,
                    )
                else:
                    results = await retriever.retrieve_hybrid(
                        question=question,
                        knowledge_base_id=3,
                        limit=10,
                        rerank=(name == "hybrid+rerank"),
                    )

                metrics_5 = compute_metrics(results, relevant, 5)
                metrics_10 = compute_metrics(results, relevant, 10)

                aggregates[name]["recall_5"] += metrics_5["recall"]
                aggregates[name]["recall_10"] += metrics_10["recall"]
                aggregates[name]["mrr"] += metrics_5["mrr"]
                if metrics_5["recall"] > 0:
                    aggregates[name]["hit"] += 1

                hit = "✓" if metrics_5["recall"] > 0 else "✗"
                print(
                    f"    {name:12s} {hit} "
                    f"R@5={metrics_5['recall']:.2f} "
                    f"R@10={metrics_10['recall']:.2f} "
                    f"MRR={metrics_5['mrr']:.3f}"
                )

        print("=" * 90)
        print("汇总指标（三档对比）：")
        print(f"{'方式':<14s} {'Recall@5':>9s} {'Recall@10':>10s} {'MRR':>7s} {'命中率':>7s}")
        for name in retrievers:
            agg = aggregates[name]
            print(
                f"{name:<14s} "
                f"{agg['recall_5'] / total:>9.3f} "
                f"{agg['recall_10'] / total:>10.3f} "
                f"{agg['mrr'] / total:>7.3f} "
                f"{agg['hit'] / total:>7.2f}"
            )


if __name__ == "__main__":
    asyncio.run(main())
