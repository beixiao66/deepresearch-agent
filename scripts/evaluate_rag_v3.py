"""RAG 离线评估脚本：同主题多文档语料，文档级 + 片段级金标。

语料：RAG评估语料库（knowledge_base_id=3）
  doc 1  = 01-RAG入门概念.md
  doc 4  = 03-RAG生产落地实践.txt
  doc 7  = 05-RAG评估方法.md
  doc 10 = 07-LangGraph状态与人工介入.txt
  doc 11 = 08-LangGraph多智能体.md
  doc 14 = 10-向量数据库选型.txt
  doc 15 = 02-文本切块与检索优化.pdf
  doc 16 = 04-RAG与大模型幻觉.pdf
  doc 17 = 06-LangGraph基础入门.pdf
  doc 18 = 09-向量数据库原理.pdf
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

KNOWLEDGE_BASE_ID = 3

# ===== 文档 ID 对照（只保留最新上传的文档）=====
D_RAG_BASIC = 1          # 01-RAG入门概念.md
D_PROD = 4               # 03-RAG生产落地实践.txt
D_EVAL = 7               # 05-RAG评估方法.md
D_LG_HITL = 10           # 07-LangGraph状态与人工介入.txt
D_LG_MULTI = 11          # 08-LangGraph多智能体.md
D_VEC_CHOICE = 14        # 10-向量数据库选型.txt
D_CHUNK_PDF = 15         # 02-文本切块与检索优化.pdf
D_HALLU_PDF = 16         # 04-RAG与大模型幻觉.pdf
D_LG_PDF = 17            # 06-LangGraph基础入门.pdf
D_VEC_PDF = 18           # 09-向量数据库原理.pdf

# ===== 片段级金标：锚定唯一关键词，命中该关键词的片段才算相关 =====
# 文档级金标 + 唯一锚定词（该词只出现在相关文档中）
EVALUATION_SET = [
    # ===== 语义型（向量优势场景）=====
    {
        "question": "RAG 的全称是什么，它的核心思想是什么？",
        "relevant": [D_RAG_BASIC],
        "anchor": "Retrieval-Augmented Generation",
        "type": "语义",
    },
    {
        "question": "大语言模型生成内容看似合理但实际错误，这个问题叫什么？",
        "relevant": [D_HALLU_PDF],
        "anchor": "幻觉",
        "type": "语义",
    },
    {
        "question": "切块太小和切块太大分别有什么问题？",
        "relevant": [D_CHUNK_PDF],
        "anchor": "语义不完整",
        "type": "语义",
    },
    {
        "question": "为什么模型回答必须基于检索资料而不是自由发挥？",
        "relevant": [D_HALLU_PDF],
        "anchor": "禁止自由发挥",
        "type": "语义",
    },
    {
        "question": "多智能体相比单个 Agent 有什么代价？",
        "relevant": [D_LG_MULTI],
        "anchor": "成本和延迟成倍增加",
        "type": "语义",
    },
    {
        "question": "知识库文档会过期，生产系统应该怎么处理？",
        "relevant": [D_PROD],
        "anchor": "幽灵向量",
        "type": "语义",
    },
    {
        "question": "为什么说向量检索和关键词检索要结合起来用？",
        "relevant": [D_CHUNK_PDF],
        "anchor": "语义漂移",
        "type": "语义",
    },
    {
        "question": "人工介入为什么要在关键决策点暂停等用户确认？",
        "relevant": [D_LG_HITL],
        "anchor": "不可逆操作",
        "type": "语义",
    },
    {
        "question": "向量数据库为什么比普通关系数据库更适合向量检索？",
        "relevant": [D_VEC_PDF],
        "anchor": "高维向量",
        "type": "语义",
    },
    {
        "question": "评估 RAG 系统有哪些常用指标？",
        "relevant": [D_EVAL],
        "anchor": "MRR",
        "type": "语义",
    },
    # ===== 关键词型（BM25 优势场景）=====
    {
        "question": "chunk_size 和 chunk_overlap 分别代表什么？",
        "relevant": [D_CHUNK_PDF],
        "anchor": "chunk_overlap",
        "type": "关键词",
    },
    {
        "question": "LangChain 的 RecursiveCharacterTextSplitter 是什么？",
        "relevant": [D_CHUNK_PDF],
        "anchor": "RecursiveCharacterTextSplitter",
        "type": "关键词",
    },
    {
        "question": "MemorySaver 在 LangGraph 里是干什么的？",
        "relevant": [D_LG_PDF],
        "anchor": "MemorySaver",
        "type": "关键词",
    },
    {
        "question": "add_conditional_edges 是做什么的？",
        "relevant": [D_LG_PDF],
        "anchor": "add_conditional_edges",
        "type": "关键词",
    },
    {
        "question": "thread_id 配置在哪个字段里？",
        "relevant": [D_LG_HITL],
        "anchor": "configurable",
        "type": "关键词",
    },
    {
        "question": "Command 的 resume 参数怎么用？",
        "relevant": [D_LG_HITL],
        "anchor": "Command",
        "type": "关键词",
    },
    {
        "question": "text-embedding-v4 的维度是多少？",
        "relevant": [D_VEC_PDF],
        "anchor": "text-embedding-v4",
        "type": "关键词",
    },
    {
        "question": "Distance.COSINE 是什么距离度量？",
        "relevant": [D_VEC_PDF],
        "anchor": "Distance.COSINE",
        "type": "关键词",
    },
    {
        "question": "PointStruct 包含哪几个字段？",
        "relevant": [D_VEC_PDF],
        "anchor": "PointStruct",
        "type": "关键词",
    },
    {
        "question": "PyPDFLoader 是做什么的？",
        "relevant": [D_RAG_BASIC],
        "anchor": "PyPDFLoader",
        "type": "关键词",
    },
    {
        "question": "FAISS 和 Qdrant 分别是什么？",
        "relevant": [D_RAG_BASIC],
        "anchor": "FAISS",
        "type": "关键词",
    },
    {
        "question": "ES 8.x 支持向量检索吗？",
        "relevant": [D_VEC_CHOICE],
        "anchor": "ES 8.x",
        "type": "关键词",
    },
    {
        "question": "Redis 8.x 的向量索引适合什么场景？",
        "relevant": [D_VEC_CHOICE],
        "anchor": "Redis 8.x",
        "type": "关键词",
    },
    {
        "question": "NDCG 是什么指标？",
        "relevant": [D_EVAL],
        "anchor": "NDCG",
        "type": "关键词",
    },
    {
        "question": "bm25 函数在 FTS5 里返回正数还是负数？",
        "relevant": [D_CHUNK_PDF],
        "anchor": "bm25()",
        "type": "关键词",
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
        anchor: str,
        k: int,
) -> dict:
    """文档级 + 片段级（锚定词）双金标计算。"""
    relevant_ids_set = set(relevant_document_ids)

    # ---- 文档级 ----
    retrieved_relevant_documents = {
        result.document_id
        for result in results[:k]
        if result.document_id in relevant_ids_set
    }
    doc_recall = (
        len(retrieved_relevant_documents) / len(relevant_ids_set)
    )

    # ---- 片段级：锚定词必须出现在检索片段的文本里 ----
    anchor_text = anchor.lower()
    retrieved_anchor_chunks = [
        result
        for result in results[:k]
        if result.document_id in relevant_ids_set
        and anchor_text in (result.text or "").lower()
    ]
    chunk_recall = 1.0 if retrieved_anchor_chunks else 0.0

    # ---- MRR（文档级）----
    mrr = 0.0
    seen: set[int] = set()
    for rank, result in enumerate(results, start=1):
        if (
            result.document_id in relevant_ids_set
            and result.document_id not in seen
        ):
            mrr = 1.0 / rank
            break
        seen.add(result.document_id)

    # ---- MRR（片段级：锚定词出现的片段）----
    chunk_mrr = 0.0
    for rank, result in enumerate(results, start=1):
        if (
            result.document_id in relevant_ids_set
            and anchor_text in (result.text or "").lower()
        ):
            chunk_mrr = 1.0 / rank
            break

    return {
        "doc_recall_5": doc_recall,
        "chunk_recall_5": chunk_recall,
        "doc_mrr": mrr,
        "chunk_mrr": chunk_mrr,
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

        total = len(EVALUATION_SET)
        aggregates = {
            name: {
                "doc_recall_5": 0.0,
                "chunk_recall_5": 0.0,
                "doc_mrr": 0.0,
                "chunk_mrr": 0.0,
            }
            for name in retrievers
        }

        print(f"评估知识库: knowledge_base_id={KNOWLEDGE_BASE_ID}")
        print(f"评估问题数: {total}（语义 {sum(1 for i in EVALUATION_SET if i['type']=='语义')} / 关键词 {sum(1 for i in EVALUATION_SET if i['type']=='关键词')}）")
        print("=" * 100)

        for index, item in enumerate(EVALUATION_SET, start=1):
            question = item["question"]
            relevant = item["relevant"]
            anchor = item["anchor"]

            print(
                f"[{index:02d}/{total}] [{item['type']}] "
                f"{question[:38]}"
            )

            for name, retriever in retrievers.items():
                if name == "dense":
                    results = await retriever.retrieve(
                        question=question,
                        knowledge_base_id=KNOWLEDGE_BASE_ID,
                        limit=10,
                    )
                else:
                    results = await retriever.retrieve_hybrid(
                        question=question,
                        knowledge_base_id=KNOWLEDGE_BASE_ID,
                        limit=10,
                        rerank=(name == "hybrid+rerank"),
                    )

                metrics = compute_metrics(
                    results, relevant, anchor, 5
                )

                aggregates[name]["doc_recall_5"] += metrics["doc_recall_5"]
                aggregates[name]["chunk_recall_5"] += metrics["chunk_recall_5"]
                aggregates[name]["doc_mrr"] += metrics["doc_mrr"]
                aggregates[name]["chunk_mrr"] += metrics["chunk_mrr"]

                chunk_hit = "OK" if metrics["chunk_recall_5"] > 0 else "XX"
                print(
                    f"    {name:12s} {chunk_hit} "
                    f"DocR@5={metrics['doc_recall_5']:.2f} "
                    f"ChunkR@5={metrics['chunk_recall_5']:.2f} "
                    f"DocMRR={metrics['doc_mrr']:.3f} "
                    f"ChunkMRR={metrics['chunk_mrr']:.3f}"
                )

        print("=" * 100)
        print("汇总指标（三档对比，{total} 题）：")
        print(
            f"{'方式':<14s} {'DocR@5':>8s} {'ChunkR@5':>9s} "
            f"{'DocMRR':>8s} {'ChunkMRR':>9s}"
        )
        for name in retrievers:
            agg = aggregates[name]
            print(
                f"{name:<14s} "
                f"{agg['doc_recall_5'] / total:>8.3f} "
                f"{agg['chunk_recall_5'] / total:>9.3f} "
                f"{agg['doc_mrr'] / total:>8.3f} "
                f"{agg['chunk_mrr'] / total:>9.3f}"
            )


if __name__ == "__main__":
    asyncio.run(main())
