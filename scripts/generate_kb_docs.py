"""生成一套多格式知识库测试语料，覆盖项目支持的全部文档类型。

用途：本地没有真实文档时，快速造一批可检索、可评估的中文语料，用来验证
「上传 → 解析 → 切分 → 向量化 → 双写（Qdrant + FTS5）→ 混合检索」整条链路。

覆盖格式（与 app/services/document_parser.py 支持的一致）：
    .md  .txt  .html  .csv  .docx  .xlsx  .pptx  .pdf

用法：
    python scripts/generate_kb_docs.py
    python scripts/generate_kb_docs.py --out "C:\\Users\\me\\Desktop\\知识库"

注意：PDF 由本脚本手写 PDF 语法生成（不依赖 reportlab 等库），
因此内容为纯 ASCII 英文——正好也能顺带验证检索对英文文档的处理。
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches, Pt as PptPt

DEFAULT_OUTPUT = Path.home() / "Desktop" / "知识库"


# ============================================================
# 1. Markdown：RAG 基础与工作流
# ============================================================

RAG_BASICS_MD = """# RAG 基础与工作流

## 什么是 RAG

RAG（Retrieval-Augmented Generation，检索增强生成）把信息检索与大语言模型生成结合起来：
先从外部知识库检索与问题相关的片段，再把片段作为上下文交给模型生成答案。

它主要解决三个问题：

1. **知识过时**：模型训练数据有截止时间，检索可以引入最新资料
2. **幻觉**：答案必须依据检索到的原文，减少凭空编造
3. **私有数据**：企业内部文档不必进入训练集，只进检索库

## 标准工作流

### 索引阶段（离线）

文档加载 → 文本切分 → 向量化 → 写入向量库；同时写入关键词索引。

### 检索阶段（在线）

问题向量化 → 相似度召回 → 重排精排 → 按分数与去重规则组装上下文。

### 生成阶段

把上下文与问题一起交给 LLM，要求输出带引用编号的答案，并在后处理阶段
删除超出来源数量的引用编号（模型会编造不存在的引用）。

## 与微调的取舍

| 维度 | RAG | 微调 |
| --- | --- | --- |
| 知识更新 | 替换文档即可，分钟级 | 需要重新训练 |
| 可解释性 | 强，可回溯到原文片段 | 弱 |
| 单次成本 | 检索 + 推理 | 训练 + 推理 |
| 适合场景 | 私有知识问答、时效性内容 | 固定风格、固定格式输出 |

## 常见失败模式

- **检索不到**：切分粒度过大，或 embedding 模型与领域语料不匹配
- **检索到但答错**：上下文过长，关键片段被淹没在中间位置
- **编造引用**：模型写出不存在的 `[n]`，必须在输出后处理阶段过滤
- **多跳问题失败**：单个查询词无法覆盖需要串联多个文档的问题，需要拆分子问题
"""


# ============================================================
# 2. 纯文本：向量检索原理
# ============================================================

VECTOR_SEARCH_TXT = """向量检索原理

一、文本向量化（Embedding）

Embedding 模型把一段文本映射成固定维度的稠密向量，语义相近的文本在向量空间中
距离更近。常见维度为 768、1024、1536。维度越高表达能力越强，但存储与计算成本
同步上升。

本项目使用 text-embedding-v4，输出 1024 维向量，并且是批量调用（一次请求提交
多条文本），避免逐条请求带来的网络往返开销。批量大小需要控制，过大容易触发
服务端的请求体限制。

二、相似度度量

1. 余弦相似度：只看向量方向，不受长度影响，是文本检索最常用的度量
2. 点积：同时受方向和模长影响，向量归一化后与余弦等价
3. 欧氏距离：对模长敏感，文本检索中较少单独使用

三、近似最近邻（ANN）

精确检索需要与库中每个向量计算距离，复杂度 O(N)，千万级数据下不可接受。
ANN 通过牺牲少量召回率换取数量级的速度提升，主流算法有：

- HNSW：分层可导航小世界图，查询快、内存占用高，是目前最常用的选择
- IVF：倒排文件，先聚类再在若干簇内搜索，内存友好
- PQ：乘积量化，把向量压缩成短码，适合超大规模但精度损失明显

四、过滤检索

实际业务几乎不会在全库检索，而是先按知识库 ID、文档类型、时间范围过滤，
再在子集内做向量检索。过滤与检索的执行顺序会显著影响性能：先过滤再检索
通常更快，但需要向量库支持带过滤条件的索引扫描。

五、为什么还需要关键词检索

稠密向量擅长语义匹配，但对以下情况表现不佳：

- 精确的专有名词、型号、错误码
- 数字与单位
- 中文短查询（分词质量直接影响关键词路的效果）

因此工程上普遍采用向量 + 关键词的双路召回，再用 RRF 等策略融合。
"""


# ============================================================
# 3. HTML：Qdrant 与向量数据库
# ============================================================

QDRANT_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Qdrant 与向量数据库</title>
</head>
<body>
  <h1>Qdrant 与向量数据库</h1>

  <h2>一、向量数据库解决什么问题</h2>
  <p>
    向量数据库在近似最近邻检索之上，补齐了工程化能力：持久化存储、增删改、
    元数据过滤、水平扩展、快照与恢复。直接用 FAISS 这类库做检索，还需要自己
    实现这些部分。
  </p>

  <h2>二、Qdrant 核心概念</h2>
  <ul>
    <li><strong>Collection（集合）</strong>：一组向量的逻辑容器，创建时必须指定向量维度与距离度量</li>
    <li><strong>Point（点）</strong>：一条记录，由 id、vector、payload 三部分组成</li>
    <li><strong>Payload（负载）</strong>：附加的元数据，例如 document_id、chunk_index、knowledge_base_id</li>
    <li><strong>Filter（过滤）</strong>：基于 payload 的条件筛选，可与向量检索组合成一次请求</li>
  </ul>

  <h2>三、常用检索参数</h2>
  <table border="1" cellpadding="6">
    <tr><th>参数</th><th>含义</th><th>调优建议</th></tr>
    <tr><td>limit</td><td>返回条数</td><td>召回阶段取大一些，交给重排裁剪</td></tr>
    <tr><td>score_threshold</td><td>分数下限</td><td>过滤明显不相关的片段</td></tr>
    <tr><td>with_payload</td><td>是否返回元数据</td><td>需要引用溯源时必须开启</td></tr>
  </table>

  <h2>四、删除与一致性</h2>
  <p>
    删除文档时要同步清理三处：原始文件、向量库中的点、关键词索引中的行。
    任何一处遗漏都会造成「检索得到但文件不存在」或「文件删了索引还在」的脏数据。
  </p>

  <h2>五、部署形态</h2>
  <p>
    本地开发通常用 Docker 单机部署，默认端口 6333（HTTP）与 6334（gRPC）。
    生产环境需要考虑副本数、分片数、快照策略与磁盘类型。
  </p>
</body>
</html>
"""


# ============================================================
# 4. CSV：检索方案对比
# ============================================================

RETRIEVAL_COMPARISON_CSV = [
    ["方案", "原理", "优点", "缺点", "适用场景"],
    ["纯向量检索", "把问题和片段映射到同一向量空间，按余弦相似度召回", "语义匹配强，能处理同义改写", "专有名词与数字匹配弱", "语义型问答"],
    ["BM25 关键词检索", "基于词频与逆文档频率的稀疏检索", "精确匹配强，可解释", "中文分词依赖强，无同义泛化", "精确查找、术语检索"],
    ["混合检索（RRF）", "两路召回后用倒数排名融合", "兼顾语义与精确匹配，无需调权重", "多一次检索开销", "通用召回，生产默认"],
    ["交叉编码器重排", "把问题与候选片段拼接后交给模型打分", "精度最高，显著提升 Top 位次", "无法用于全库召回，只适合精排", "召回后的精排阶段"],
    ["多查询改写", "用 LLM 把问题改写成多个查询词分别检索", "提升召回覆盖面", "增加一次模型调用与延迟", "复杂问题、多跳问题"],
    ["子问题拆分", "把复杂问题拆成多个子问题分别检索再汇总", "覆盖多跳推理", "实现复杂，成本高", "研究型任务"],
]


# ============================================================
# 5. Markdown：LangGraph 多 Agent 编排
# ============================================================

LANGGRAPH_MD = """# LangGraph 多 Agent 编排

## 为什么用图而不是链

链式编排（Chain）是单向的，难以表达分支、循环和人工介入。LangGraph 用
「状态 + 节点 + 边」描述流程，天然支持条件分支、并行分发和中断恢复。

## 三个核心概念

### State（状态）

一个 TypedDict，所有节点读写同一份状态。需要并行合并的字段用 reducer 注解：

```python
class ResearchState(TypedDict):
    question: str
    sub_answers: Annotated[list[dict], add_sub_answers]
    token_usage: Annotated[dict, merge_token_usage]
```

`add_sub_answers` 把多个并行子 Agent 的结果追加合并，`merge_token_usage`
把各阶段的 token 用量累加。没有 reducer 的字段是覆盖语义。

### Node（节点）

一个普通函数或协程，接收状态、返回状态更新。节点应该是幂等的，
尤其是中断点之前的节点——恢复执行时会重放。

### Edge（边）

- 普通边：`add_edge("plan", "review")`
- 条件边：`add_conditional_edges("dispatch", router, ["researcher"])`

## Send API：并行分发

条件边函数返回 `Send` 列表，即可把同一节点并行实例化多次：

```python
def _fanout(state):
    return [
        Send("researcher", {"question": q, "knowledge_base_id": state["knowledge_base_id"]})
        for q in state["plan"].sub_questions
    ]
```

每个子 Agent 拿到独立的状态分片，全部完成后才汇聚到下一个节点。
注意：子 Agent 的返回值只有带 reducer 的字段才会正确合并。

## Human-in-the-loop：interrupt

`interrupt()` 会暂停图执行并把参数返回给调用方，等待人工决策：

```python
def _review_plan(state):
    decision = interrupt({"title": "研究计划审核", "sub_questions": state["plan"].sub_questions})
    if not decision.get("approved"):
        raise ValueError("Research plan rejected by user")
    return {"plan": state["plan"]}
```

恢复执行用 `Command(resume=...)`，并且必须使用同一个 `thread_id`。

## Checkpointer：状态持久化

- `MemorySaver`：进程内内存，重启即丢，只适合测试
- `AsyncSqliteSaver`：落盘到 SQLite，进程重启后同一 thread_id 仍可恢复中断现场

持久化 checkpointer 是「人工确认」这类长事务的前提：用户可能隔几分钟甚至
隔天才点确认，进程不能一直挂着。

### 序列化白名单

checkpoint 用 `JsonPlusSerializer` 序列化状态。状态里出现的自定义类型必须
显式注册，否则反序列化时会告警甚至被拒绝：

```python
_CHECKPOINT_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=(("app.schemas.research", "ResearchPlan"),)
)
```

## 资源生命周期

`AsyncSqliteSaver` 底层是 aiosqlite，连接的后台线程不是守护线程——
忘记关闭会让进程无法退出。正确做法是在应用 lifespan 的关闭阶段调用
`await checkpointer.conn.close()`。
"""


# ============================================================
# 6. 纯文本：文档切分与 Embedding 策略
# ============================================================

CHUNKING_TXT = """文档切分与 Embedding 策略

一、为什么要切分

Embedding 模型有输入长度上限，整篇文档塞进去会丢失细节；检索也需要更细的
粒度才能定位到具体段落。切分就是把长文档拆成适合检索的片段（chunk）。

二、切分粒度

经验区间是 300 到 800 个中文字符。

- 太小：单片段信息不完整，模型拿不到足够上下文
- 太大：一个片段混入多个主题，向量被平均化，检索精度下降

本项目的评测显示，片段级指标（ChunkMRR）对切分粒度非常敏感，
粒度合适时重排带来的提升才明显。

三、重叠窗口

相邻片段之间保留 10% 到 20% 的重叠，避免关键句子正好被切断在两个片段之间。
代价是存储与索引量增加，检索时也可能召回内容重复的片段，需要在去重阶段处理。

四、切分边界优先级

1. 优先按标题层级切（Markdown 的 #、##）
2. 其次按段落（连续空行）
3. 再按句子（中文的。！？）
4. 最后才按固定长度硬切

按语义边界切分能让每个片段自成一体，显著好于定长硬切。

五、Embedding 批次

批量调用可以摊薄网络往返，但要注意：

- 单次请求的文本条数有上限
- 过长的文本会拖慢整批响应
- 失败重试要按批而不是按条，否则容易放大请求量

六、中文分词与稀疏检索

SQLite FTS5 的默认 tokenizer 对中文按字符切分，效果接近 bigram，
在短查询上几乎不产生有效的关键词召回。要改善需要：

1. 换用自定义 tokenizer（如 simple 分词器扩展）
2. 或在入库前用 jieba 等工具预处理，把词用空格连接后再写入索引

注意：改动分词方案必须重建整个 FTS5 索引，历史数据不会自动重切。
"""


# ============================================================
# 7. Markdown：RAG 评估指标
# ============================================================

EVALUATION_MD = """# RAG 评估指标与离线评测

## 为什么必须做离线评估

RAG 的效果由检索与生成两段共同决定。没有量化指标时，「调了参数感觉变好了」
无法证伪，也无法判断某次改动是优化还是退化。

## 检索层指标

| 指标 | 含义 | 说明 |
| --- | --- | --- |
| Recall@K | 前 K 条结果中命中相关文档的比例 | 衡量召回能力，最重要 |
| Precision@K | 前 K 条中相关结果占比 | 衡量噪声水平 |
| MRR | 第一个相关结果排名的倒数均值 | 衡量排序质量 |
| NDCG@K | 考虑位置权重的排序质量 | 多级相关性时更合适 |

## 文档级与片段级金标

只标「哪篇文档相关」会掩盖问题：文档被召回了，但真正包含答案的片段排在第 20 位，
此时文档级指标很好看，实际效果很差。

因此需要双层金标：

- 文档级：问题对应哪几篇文档
- 片段级：答案必须包含哪些锚定词，锚定词出现在被检索片段中才算命中

片段级金标能拉开不同检索方案的差距。

## 生成层指标

- **忠实度（Faithfulness）**：答案的每个论断是否都能在检索片段中找到依据
- **答案相关性**：答案是否真正回答了问题
- **引用准确率**：正文引用编号与来源列表是否一一对应

引用准确率可以用规则校验：把正文中出现的 `[n]` 提取出来，检查 n 是否超出
来源总数。模型编造引用是高频问题，必须在输出后处理阶段拦截。

## 评测集构造

1. 选定主题，每个主题准备若干篇文档
2. 每个主题写若干问题，覆盖事实型、对比型、多跳型
3. 为每个问题标注文档级与片段级金标
4. 固定语料与问题集，任何改动都在同一套数据上对比

## 本项目实测结论

在自建语料上对比三种方案：

| 检索方式 | DocR@5 | ChunkR@5 | DocMRR | ChunkMRR |
| --- | --- | --- | --- | --- |
| 纯向量 | 0.960 | 0.960 | 0.877 | 0.814 |
| 混合（向量 + BM25 + RRF） | 0.960 | 0.960 | 0.877 | 0.814 |
| 混合 + Rerank | 1.000 | 1.000 | 0.968 | 0.968 |

两个值得说明的现象：

1. 混合检索与纯向量指标完全一致，原因是中文 FTS5 分词效果差，关键词路
   几乎没有贡献——这是一个需要如实报告的负面结论
2. 重排在片段级 MRR 上提升 0.154，说明精排阶段对最终排序影响最大
"""


# ============================================================
# 8. Markdown：后端面试高频问题
# ============================================================

INTERVIEW_MD = """# 后端面试高频问题（RAG / Agent 方向）

## 一、检索相关

**Q：为什么用了向量检索还要加 BM25？**

向量擅长语义匹配，但对专有名词、型号、错误码、数字这类精确匹配不敏感。
BM25 基于词频统计，恰好补上这块。两路召回后用 RRF 融合，不需要人工调权重，
因为 RRF 只用排名不用分数，规避了两路分数量纲不可比的问题。

**Q：RRF 为什么比加权求和更稳？**

向量相似度的取值区间和 BM25 的分数区间完全不同，加权求和需要归一化，
而归一化方式本身又是一个需要调的超参。RRF 只用「排在第几名」这一个信息，
形式是 sum(1 / (k + rank))，对分数分布不敏感，跨数据集更稳。

**Q：重排模型为什么不直接用来召回？**

交叉编码器要把问题和每个候选片段拼在一起送进模型，无法预先计算文档向量，
对全库做一遍等于对每篇文档跑一次模型推理，成本不可接受。所以它只用在
召回后的精排阶段，作用在几十条候选上。

## 二、工程相关

**Q：文档删除要注意什么？**

要同步清理三处：原始文件、向量库里的点、关键词索引里的行。少清任何一处
都会留下脏数据——检索能命中，但取原文时文件已不存在。

**Q：LLM 应用怎么做流式？**

用 SSE。服务端把事件按 `data: {json}\\n\\n` 的格式写出，客户端逐块解析。
注意两点：一是要有心跳或结束事件，否则连接可能被中间层超时断开；
二是服务端推送用的全局回调在流结束时必须清空，否则并发请求会串流。

**Q：长任务怎么做人工确认？**

用 LangGraph 的 interrupt + 持久化 checkpointer。图执行到确认节点时暂停，
状态落盘，接口返回「待确认」；用户点确认后再用 `Command(resume=...)`
带同一个 thread_id 恢复。关键是 checkpointer 必须持久化，否则进程一重启
中断现场就丢了。

**Q：Token 用量怎么统计？**

在封装层统一提取。所有 LLM 调用都经过一个封装函数，从响应的 usage_metadata
里取 input/output/total 三个值，累加到调用方传入的计数器字典里。并行节点
的计数器需要用 reducer 合并，否则会互相覆盖。

## 三、系统设计

**Q：为什么对话功能不接检索？**

研究流程是一次性任务，用户拿到报告后常有追问需求，所以引入多轮对话承接。
但对话故意不检索知识库：它面向的是快速澄清与讨论，需要依据时应走研究流程
这条有引用、可追溯的链路。两条链路都给引用会让用户分不清哪条答案更可信。

**Q：如果让你优化检索效果，你会怎么做？**

优先级从高到低：

1. 先做评估集，没有指标就没有优化方向
2. 加交叉编码器重排，投入产出比最高
3. 优化切分粒度与重叠窗口
4. 加查询改写，处理多轮追问里的指代
5. 解决中文分词问题，让关键词路真正生效
6. 最后才考虑换更大的 embedding 模型
"""


# ============================================================
# 9. Word：RAG 系统设计要点
# ============================================================

SYSTEM_DESIGN_DOCX = [
    ("h1", "RAG 系统设计要点"),
    ("p", "本文整理一套检索增强生成系统在设计阶段需要明确的决策点，"
          "按数据流顺序排列。"),
    ("h2", "一、数据接入"),
    ("p", "支持的文档类型决定了后续解析器的复杂度。常见类型包括 PDF、Markdown、"
          "纯文本、Word、Excel、PPT、CSV 与 HTML。每类格式的提取深度不同："
          "PDF 提取文本层，Excel 只取单元格文本，PPT 只取文本框，"
          "扫描件与图片内文字需要 OCR，属于另一条链路。"),
    ("bullets", [
        "统一入口：所有格式解析后输出同一种结构（文本 + 元数据）",
        "失败可重试：解析失败要记录原因并允许单文档重试，不能整批失败",
        "状态机：待处理 → 处理中 → 已完成 / 失败，前端据此展示进度",
    ]),
    ("h2", "二、索引构建"),
    ("p", "切分粒度建议 300 到 800 字符，相邻片段保留 10% 到 20% 重叠。"
          "向量化采用批量调用，写入时同步维护关键词索引，保证两路召回的数据一致。"),
    ("h2", "三、检索策略"),
    ("p", "推荐双路召回 + 融合 + 精排的三段式结构。召回阶段放宽条数，"
          "交给精排裁剪；融合阶段用 RRF 规避分数量纲问题；"
          "精排阶段用交叉编码器对候选重新打分。"),
    ("table", (
        ["阶段", "目标", "典型参数"],
        [
            ["召回", "尽量不漏", "每路 10 到 20 条"],
            ["融合", "合并两路", "RRF k 取 60"],
            ["精排", "提升头部精度", "输出 Top 3 到 5"],
        ],
    )),
    ("h2", "四、生成与引用"),
    ("p", "上下文组装时要给片段编号，并要求模型只能引用给定范围内的编号。"
          "生成后必须做一次引用校验：正文里出现的编号如果超出片段总数，"
          "说明模型编造了引用，需要删除或截断。"),
    ("h2", "五、可观测性"),
    ("p", "至少要记录三类数据：每次检索召回与精排的数量、每个阶段消耗的 token、"
          "任务的完整状态流转。没有这些数据，线上问题无法定位。"),
]

# ============================================================
# 10. Excel：项目参数表
# ============================================================

PARAMS_SHEET = (
    ["参数", "取值", "说明"],
    [
        ["Embedding 模型", "text-embedding-v4", "向量维度 1024"],
        ["向量维度", "1024", "与 Qdrant collection 创建时一致"],
        ["距离度量", "Cosine", "文本检索最常用"],
        ["生成模型", "qwen-plus", "上下文窗口 128K"],
        ["重排模型", "qwen3-rerank", "交叉编码器，独立 base_url"],
        ["切分长度", "300-800 字符", "按标题/段落/句子优先级切分"],
        ["重叠窗口", "10%-20%", "避免关键句被切断"],
        ["召回条数", "每路 10-20", "交给精排裁剪"],
        ["精排输出", "Top 3-5", "最终进入上下文的片段数"],
        ["RRF 参数 k", "60", "倒数排名融合的平滑常数"],
        ["摘要阈值", "16000 token", "超过后压缩老消息为摘要"],
        ["保留原文条数", "10 条", "摘要时保留的最近消息数"],
    ],
)

RETRIEVAL_SHEET = (
    ["检索方式", "DocR@5", "ChunkR@5", "DocMRR", "ChunkMRR"],
    [
        ["纯向量", 0.960, 0.960, 0.877, 0.814],
        ["混合（向量 + BM25 + RRF）", 0.960, 0.960, 0.877, 0.814],
        ["混合 + Rerank", 1.000, 1.000, 0.968, 0.968],
    ],
)

API_SHEET = (
    ["方法", "路径", "说明"],
    [
        ["POST", "/api/v1/knowledge-bases", "创建知识库"],
        ["GET", "/api/v1/knowledge-bases", "知识库列表"],
        ["POST", "/api/v1/knowledge-bases/{id}/documents", "上传文档并自动索引"],
        ["GET", "/api/v1/knowledge-bases/{id}/documents", "文档列表（含状态）"],
        ["DELETE", "/api/v1/knowledge-bases/{id}/documents/{doc_id}", "删除文档并清理三处存储"],
        ["POST", "/api/v1/knowledge-bases/{id}/search", "知识库检索"],
        ["POST", "/api/v1/research", "创建研究（SSE，到计划确认暂停）"],
        ["POST", "/api/v1/research/tasks/{id}/approve", "确认或拒绝计划（SSE）"],
        ["GET", "/api/v1/research/tasks", "研究任务列表"],
        ["POST", "/api/v1/chat", "多轮对话"],
        ["DELETE", "/api/v1/chat/conversations/{id}", "删除会话及其对话历史"],
    ],
)


# ============================================================
# 11. PPT：项目汇报
# ============================================================

SLIDES = [
    ("DeepResearch Agent", "基于 RAG + LangGraph 的深度研究助手"),
    ("要解决的问题", "通用大模型无法回答私有知识问题，且答案缺少可追溯的依据。"
                     "目标是让系统先查资料、再给结论，并把引用编号与原文片段对应起来。"),
    ("系统架构", "文档入库：解析 → 切分 → 向量化 → 双写 Qdrant 与 FTS5\n"
                 "混合检索：向量 + BM25 → RRF 融合 → 交叉编码器精排\n"
                 "研究编排：规划 → 人工确认 → 并行子 Agent → 聚合报告"),
    ("研究主流程", "plan 生成子问题 → review 中断等人工确认 → dispatch 用 Send 并行分发 → "
                   "researcher 各自检索并作答 → report 聚合生成带引用的报告"),
    ("关键技术选型", "LangGraph：状态图 + interrupt + 持久化 checkpointer\n"
                     "Qdrant：向量检索与元数据过滤\n"
                     "SQLite FTS5：关键词召回\n"
                     "qwen3-rerank：交叉编码器精排"),
    ("评估结果", "自建 10 篇文档语料、25 条问题、文档级 + 片段级双金标。\n"
                 "混合 + Rerank 方案：DocR@5 1.000，ChunkMRR 0.968，"
                 "相比纯向量在片段级 MRR 上提升 0.154。"),
    ("已知局限", "中文 FTS5 分词效果差，关键词路增益有限\n"
                 "扫描件不支持 OCR\n"
                 "PDF 仅提取文本层，不处理图片内文字"),
]


# ============================================================
# 12. PDF（英文，手写 PDF 语法）
# ============================================================
PDF_LINES = [
    "Retrieval-Augmented Generation: An Overview",
    "",
    "1. Definition",
    "RAG combines an information retrieval system with a large language model.",
    "Instead of relying only on parameters learned during training, the model",
    "receives retrieved passages as context and grounds its answer in them.",
    "",
    "2. Why it matters",
    "- Knowledge can be updated by replacing documents, without retraining.",
    "- Answers can cite the exact passages they are based on.",
    "- Private data stays in the retrieval store instead of the model weights.",
    "",
    "3. Indexing pipeline",
    "Documents are parsed, split into chunks of roughly 300 to 800 characters",
    "with 10 to 20 percent overlap, embedded into dense vectors, and written to",
    "a vector database. A sparse keyword index is usually maintained in parallel.",
    "",
    "4. Retrieval pipeline",
    "Two recall paths are common: dense vector search for semantic matching and",
    "BM25 for exact term matching. Their result lists are merged, typically with",
    "Reciprocal Rank Fusion, which uses ranks instead of raw scores and therefore",
    "avoids the problem of incompatible score scales.",
    "",
    "5. Reranking",
    "A cross-encoder scores each candidate by reading the query and the passage",
    "together. It is far more accurate than vector similarity but too expensive",
    "to run over an entire corpus, so it is applied only to the merged candidate",
    "list, typically a few dozen passages.",
    "",
    "6. Generation and citation",
    "Selected passages are numbered and passed to the model, which is instructed",
    "to cite them. Because models sometimes invent citation numbers, a post",
    "processing step should remove any reference that exceeds the passage count.",
    "",
    "7. Evaluation",
    "Recall at K measures how often relevant documents appear in the top K",
    "results. MRR measures the rank of the first relevant result. Chunk level",
    "ground truth, where an anchor phrase must appear inside the retrieved",
    "chunk, exposes differences that document level metrics hide.",
    "",
    "8. Common failure modes",
    "- Chunks too large: multiple topics blended into one averaged vector.",
    "- Chunks too small: not enough context for the model to answer.",
    "- Query and document phrasing too different: recall collapses.",
    "- Long context: the key passage is buried and effectively ignored.",
]


# ============================================================
# 13. 中文长文（HTML：可直接上传，也可浏览器打印成 PDF）
# ============================================================

CN_PDF_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>RAG 系统综述</title>
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
    font-size: 10.5pt;
    line-height: 1.75;
    color: #1a1a1a;
  }
  h1 { font-size: 19pt; margin: 0 0 4px; }
  h2 { font-size: 13pt; margin: 18px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 3px; }
  p { margin: 6px 0; }
  ul { margin: 6px 0; padding-left: 20px; }
  li { margin: 3px 0; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.5pt; }
  th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; }
  th { background: #f2f2f2; }
  .subtitle { color: #666; font-size: 10pt; margin-bottom: 12px; }
</style>
</head>
<body>
  <h1>RAG 系统综述</h1>
  <p class="subtitle">检索增强生成的原理、工程实现与评估方法</p>

  <h2>一、什么是 RAG</h2>
  <p>
    检索增强生成（Retrieval-Augmented Generation）把信息检索与大语言模型生成结合：
    先从外部知识库检索与问题相关的片段，再把片段作为上下文交给模型生成答案。
    它解决三个问题——模型知识过时、幻觉、无法引用私有资料。
  </p>

  <h2>二、索引与检索流程</h2>
  <ul>
    <li>索引阶段：文档加载 → 文本切分 → 向量化 → 写入向量库与关键词索引</li>
    <li>检索阶段：问题向量化 → 双路召回 → 排名融合 → 交叉编码器精排</li>
    <li>生成阶段：片段编号后组装上下文，要求模型只引用给定范围内的编号</li>
  </ul>

  <h2>三、混合检索与重排</h2>
  <p>
    稠密向量擅长语义匹配，但对专有名词、型号、错误码这类精确匹配不敏感；
    BM25 基于词频统计，恰好补上这块。两路结果用倒数排名融合（RRF）合并，
    只使用排名而不使用分数，规避了两路分数量纲不可比的问题。
  </p>
  <p>
    交叉编码器把问题与候选片段拼接后一起送入模型打分，精度显著高于向量相似度，
    但无法预先计算文档向量，因此只用于召回后的精排阶段，作用在几十条候选上。
  </p>

  <h2>四、评估指标</h2>
  <table>
    <tr><th>指标</th><th>含义</th><th>用途</th></tr>
    <tr><td>Recall@K</td><td>前 K 条中命中相关文档的比例</td><td>衡量召回能力</td></tr>
    <tr><td>MRR</td><td>第一个相关结果排名的倒数均值</td><td>衡量排序质量</td></tr>
    <tr><td>NDCG@K</td><td>考虑位置权重的排序质量</td><td>多级相关性场景</td></tr>
    <tr><td>忠实度</td><td>答案论断能否在片段中找到依据</td><td>衡量生成质量</td></tr>
  </table>
  <p>
    只标注「哪篇文档相关」会掩盖问题：文档被召回了，但包含答案的片段排在第 20 位，
    文档级指标依然好看。因此需要文档级与片段级双层金标。
  </p>

  <h2>五、常见失败模式</h2>
  <ul>
    <li>切分粒度过大：一个片段混入多个主题，向量被平均化，检索精度下降</li>
    <li>切分粒度过小：片段信息不完整，模型缺少足够上下文</li>
    <li>上下文过长：关键片段被淹没在中间位置，实际上被忽略</li>
    <li>编造引用：模型生成不存在的引用编号，必须在后处理阶段过滤</li>
    <li>中文分词不佳：关键词路几乎不产生有效召回，等于退化为单路检索</li>
  </ul>

  <h2>六、工程检查清单</h2>
  <ul>
    <li>删除文档时同步清理原始文件、向量库中的点、关键词索引中的行</li>
    <li>对话或研究任务的长事务要用持久化 checkpoint，进程重启后可恢复</li>
    <li>所有模型调用统一统计 token 用量，并行节点的计数器需要合并而不是覆盖</li>
    <li>检索与生成的关键中间结果落库，否则线上问题无法定位</li>
  </ul>
</body>
</html>
"""

# 说明：中文 PDF 没有用无头浏览器生成——本机 Chrome/Edge 的 headless 模式
# 会在不做任何工作的情况下直接退出（--print-to-pdf / --dump-dom / --screenshot
# 全部无输出）。因此改为输出 HTML：既能直接上传（解析器支持 .html），
# 也能用浏览器「打印 → 另存为 PDF」一步转成中文 PDF，无需任何额外依赖。
CN_PDF_HINT = (
    "如需中文 PDF：用浏览器打开该文件 → Ctrl+P → 目标选择「另存为 PDF」→ "
    "保存到同一目录即可"
)


# ============================================================
# 生成函数
# ============================================================


def write_text(path: Path, content: str) -> None:
    # 不带 BOM 的 UTF-8：解析器按 utf-8 读取，BOM 会污染首行首列
    path.write_text(content, encoding="utf-8")


def write_csv_file(path: Path, rows: list[list[str]]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def write_docx(path: Path, blocks) -> None:
    document = Document()
    for kind, payload in blocks:
        if kind == "h1":
            document.add_heading(payload, level=1)
        elif kind == "h2":
            document.add_heading(payload, level=2)
        elif kind == "p":
            paragraph = document.add_paragraph(payload)
            paragraph.paragraph_format.space_after = Pt(6)
        elif kind == "bullets":
            for item in payload:
                document.add_paragraph(item, style="List Bullet")
        elif kind == "table":
            header, body = payload
            table = document.add_table(rows=1, cols=len(header))
            table.style = "Light Grid Accent 1"
            for index, title in enumerate(header):
                table.rows[0].cells[index].text = title
            for row in body:
                cells = table.add_row().cells
                for index, value in enumerate(row):
                    cells[index].text = str(value)
    document.save(path)


def write_xlsx(path: Path, sheets) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F5597")

    for title, (header, body) in sheets:
        sheet = workbook.create_sheet(title=title)
        sheet.append(header)
        for cell in sheet[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for row in body:
            sheet.append(row)
        for index, column in enumerate(sheet.columns, start=1):
            width = max(
                len(str(cell.value or "")) for cell in column
            )
            # 中文按两个字符宽度估算
            sheet.column_dimensions[get_column_letter(index)].width = min(
                max(width * 1.6 + 4, 12), 48
            )
        sheet.freeze_panes = "A2"

    workbook.save(path)


def write_pptx(path: Path, slides) -> None:
    presentation = Presentation()
    title_layout = presentation.slide_layouts[0]
    body_layout = presentation.slide_layouts[1]

    first_title, first_subtitle = slides[0]
    slide = presentation.slides.add_slide(title_layout)
    slide.shapes.title.text = first_title
    slide.placeholders[1].text = first_subtitle

    for title, body in slides[1:]:
        slide = presentation.slides.add_slide(body_layout)
        slide.shapes.title.text = title
        frame = slide.placeholders[1].text_frame
        frame.text = body.split("\n")[0]
        for line in body.split("\n")[1:]:
            frame.add_paragraph().text = line
        for paragraph in frame.paragraphs:
            for run in paragraph.runs:
                run.font.size = PptPt(16)

    presentation.save(path)


def write_pdf(path: Path, lines: list[str]) -> None:
    """手写最小 PDF：单页 A4 + Helvetica，内容必须是 ASCII。"""
    content = ["BT", "/F1 11 Tf", "15 TL", "56 786 Td"]
    for line in lines:
        escaped = (
            line.replace("\\", r"\\")
            .replace("(", r"\(")
            .replace(")", r"\)")
        )
        content.append(f"({escaped}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode()

    path.write_bytes(bytes(out))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"输出目录（默认 {DEFAULT_OUTPUT}）",
    )
    args = parser.parse_args()
    output: Path = args.out
    output.mkdir(parents=True, exist_ok=True)

    tasks = [
        ("01-RAG基础与工作流.md", lambda p: write_text(p, RAG_BASICS_MD)),
        ("02-向量检索原理.txt", lambda p: write_text(p, VECTOR_SEARCH_TXT)),
        ("03-Qdrant与向量数据库.html", lambda p: write_text(p, QDRANT_HTML)),
        ("04-检索方案对比.csv", lambda p: write_csv_file(p, RETRIEVAL_COMPARISON_CSV)),
        ("05-LangGraph多Agent编排.md", lambda p: write_text(p, LANGGRAPH_MD)),
        ("06-文档切分与Embedding策略.txt", lambda p: write_text(p, CHUNKING_TXT)),
        ("07-RAG评估指标与方法.md", lambda p: write_text(p, EVALUATION_MD)),
        ("08-后端面试高频问题.md", lambda p: write_text(p, INTERVIEW_MD)),
        ("09-RAG系统设计要点.docx", lambda p: write_docx(p, SYSTEM_DESIGN_DOCX)),
        (
            "10-项目参数与评估表.xlsx",
            lambda p: write_xlsx(
                p,
                [
                    ("项目参数", PARAMS_SHEET),
                    ("检索评估", RETRIEVAL_SHEET),
                    ("API 一览", API_SHEET),
                ],
            ),
        ),
        ("11-项目汇报.pptx", lambda p: write_pptx(p, SLIDES)),
        ("12-RAG_Overview_EN.pdf", lambda p: write_pdf(p, PDF_LINES)),
        ("13-RAG系统综述_中文.html", lambda p: write_text(p, CN_PDF_HTML)),
    ]

    print(f"输出目录：{output}\n")
    ok = 0
    for filename, writer in tasks:
        target = output / filename
        try:
            writer(target)
        except Exception as exc:  # 单个文件失败不影响其余
            print(f"  FAIL  {filename:<36} {type(exc).__name__}: {exc}")
            continue
        ok += 1
        print(f"  OK    {filename:<36} {target.stat().st_size:>7} bytes")

    # 中文长文以 HTML 形式提供：可直接上传，也可手动转成 PDF
    print(f"\n提示：{CN_PDF_HINT}")

    print(f"\n完成：{ok}/{len(tasks)} 个文件")


if __name__ == "__main__":
    main()
