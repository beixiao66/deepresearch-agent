# DeepResearch Agent

基于 **RAG + LangGraph** 的智能深度研究助手：上传文档建立知识库，输入研究主题后自动规划、人工确认计划、混合检索（向量 + BM25 + 重排）、必要时联网补充，最终生成带引用来源的中文研究报告。

## 功能特性

- **知识库管理**：上传 PDF / Markdown / TXT 文档，自动完成解析 → 切分 → 向量化 → 入库，实时查看文档处理状态
- **混合检索**：向量检索（Qdrant）+ 关键词检索（SQLite FTS5 BM25）双路召回，RRF 排名融合
- **Rerank 精排**：接入百炼 `qwen3-rerank` 交叉编码器，对召回候选重新打分
- **研究编排（LangGraph）**：规划 → 人工确认 → 检索 → 证据评估 → 报告，检索不足时自动补充查询词（最多 3 轮）
- **Human-in-the-loop**：研究计划生成后暂停，由用户确认或拒绝后才继续执行
- **联网补充**：知识库证据不足时（按开关）调用 Tavily 搜索，结果带 URL 引用
- **SSE 流式进度**：研究执行过程逐步推送进度事件，前端实时展示
- **前端（Vue 3）**：知识库管理、创建研究、研究执行（计划确认 + 进度流）、研究报告（Markdown 渲染）四个页面

## 架构

```mermaid
flowchart TD
    subgraph Frontend["前端 Vue 3 (port 8080)"]
        KB[知识库管理]
        CR[创建研究]
        RUN[研究执行<br/>SSE 进度]
        REP[研究报告]
    end

    subgraph Backend["后端 FastAPI (port 8000)"]
        API[API 路由]
        GRAPH[LangGraph 主图<br/>plan → review → retrieve → report]
        RET[混合检索<br/>向量 + FTS5 + RRF + Rerank]
        WEB[Tavily 联网]
        SSE[SSE 事件流]
    end

    subgraph Storage["存储"]
        QD[(Qdrant<br/>向量库)]
        SQL[(SQLite<br/>文档/任务 + FTS5)]
    end

    API --> GRAPH
    GRAPH --> RET
    GRAPH --> WEB
    GRAPH --> SSE
    SSE --> RUN
    RET --> QD
    RET --> SQL
    API --> SQL
    KB --> API
    CR --> API
    REP --> API
```

**研究主流程**：

```text
用户输入主题
  → plan 节点：LLM 生成研究计划（子问题 + 检索关键词）
  → review 节点：interrupt 暂停，等待用户确认计划
  → retrieve 节点：混合检索（向量 + BM25 + RRF + Rerank）
      └─ 证据不足且开启联网 → Tavily 补充
  → 条件边：证据评估（条数 ≥3 且平均分 ≥0.3）→ report
      └─ 不足 → next_queries 生成补充查询词 → 重新检索（最多 3 轮）
  → report 节点：基于证据生成带引用编号的中文报告
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+、FastAPI、SQLAlchemy 2.x（async）、Pydantic v2 |
| Agent | LangChain、LangGraph（StateGraph + interrupt + checkpoint） |
| 检索 | Qdrant（向量）、SQLite FTS5（BM25）、RRF 融合、qwen3-rerank |
| 模型 | 阿里云百炼（qwen-plus / text-embedding-v4 / qwen3-rerank）、Tavily |
| 前端 | Vue 3 + Vite + vue-router + marked |

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/beixiao66/deepresearch-agent.git
cd deepresearch-agent

# Python 虚拟环境（Python 3.10-3.13）
python3.10 -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 前端依赖
cd frontend
npm install
cd ..
```

### 2. 配置环境变量

```bash
cp .env-example .env
# 填入：
# DASHSCOPE_API_KEY=你的百炼 API Key（阿里云百炼控制台）
# TAVILY_API_KEY=你的 Tavily API Key（https://tavily.com）
```

### 3. 启动基础设施

```bash
# 启动 Qdrant 向量库（Docker）
docker compose up -d
```

### 4. 启动后端

```bash
# 项目根目录执行（.env 在根目录）
uvicorn app.main:app --port 8000
# 健康检查：http://127.0.0.1:8000/health
# API 文档：http://127.0.0.1:8000/docs
```

### 5. 启动前端

```bash
cd frontend
npm run dev
# 浏览器打开 http://127.0.0.1:8080
```

### 使用流程

1. **知识库页**：创建知识库 → 上传文档（PDF/MD/TXT），等待状态变为"已完成"
2. **创建研究页**：输入研究主题、选择知识库、可选开启联网
3. **执行页**：查看生成的计划（子问题 + 关键词）→ 确认或拒绝 → 实时看 SSE 进度
4. **报告页**：阅读 Markdown 报告（含引用编号）

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/knowledge-bases` | 创建知识库 |
| GET | `/api/v1/knowledge-bases` | 知识库列表 |
| POST | `/api/v1/knowledge-bases/{id}/documents` | 上传文档（自动索引） |
| GET | `/api/v1/knowledge-bases/{id}/documents` | 文档列表（含状态） |
| DELETE | `/api/v1/knowledge-bases/{id}/documents/{doc_id}` | 删除文档（同步清理三处存储） |
| POST | `/api/v1/knowledge-bases/{id}/search` | 向量检索 |
| POST | `/api/v1/research` | 创建研究（SSE 流，到计划确认暂停） |
| POST | `/api/v1/research/tasks/{id}/approve` | 确认/拒绝计划（SSE 流，恢复执行） |
| GET | `/api/v1/research/tasks` | 研究任务列表 |
| GET | `/api/v1/research/tasks/{id}` | 任务详情（状态/计划/报告） |

## 评估结果

基于教程语料（18/19/22 章，131 个向量块）的离线评估（`scripts/evaluate_rag.py`，32 条测试问题）：

| 检索方式 | Recall@5 | Recall@10 | MRR | 命中率 |
|----------|----------|-----------|-----|--------|
| 纯向量 | 1.000 | 1.000 | 1.000 | 1.00 |
| 混合（向量+BM25+RRF） | 1.000 | 1.000 | 1.000 | 1.00 |
| 混合+Rerank | 1.000 | 1.000 | 1.000 | 1.00 |

> 说明：当前评估语料为 3 个独立主题文档，问题与文档一一对应，三档均满分。混合检索与 Rerank 的价值（关键词精确命中、语义微差排序）需在同主题多文档语料 + 片段级标注下进一步评估。

## 测试

```bash
# 后端（114 个测试，全部 mock，不消耗真实 API）
pytest -q
```

覆盖：文档解析/切分/Embedding 分批、FTS5 索引与检索、RRF 融合、Rerank、混合检索、DocumentService 状态流转、研究任务持久化、HITL 两阶段流程、SSE 事件格式、API 校验与错误处理。

## 已知局限

- **FTS5 中文分词**：SQLite FTS5 默认 tokenizer 对中文处理一般，含下划线/连字符的精确词（如 `step-by-step`）已做转义，但复杂中文分词需自定义 tokenizer
- **评估语料区分度**：当前语料主题独立，评估指标无法区分混合检索/Rerank 的增量价值，需同主题多文档语料
- **任务状态持久化**：`research_tasks` 表结构变更需手动 ALTER TABLE（SQLite 无自动迁移）
- **在线部署**：尚未部署到线上环境（本地运行验证通过）

## 项目结构

```text
deepresearch-agent/
├── app/
│   ├── api/routes/          # 路由层（chat/research/knowledge_base/documents/search）
│   ├── core/                # 配置、异常处理
│   ├── db/                  # 数据库会话、初始化
│   ├── models/              # SQLAlchemy 模型（文档、知识库、研究任务）
│   ├── repositories/        # 数据访问层
│   ├── schemas/             # Pydantic 模型
│   └── services/            # 业务层
│       ├── research_graph.py    # LangGraph 主图
│       ├── document_retriever.py # 混合检索
│       ├── reranker.py          # qwen3-rerank 重排
│       ├── sparse_*.py          # FTS5 关键词检索
│       ├── sse.py               # SSE 事件流
│       └── web_search.py        # Tavily 联网
├── frontend/                # Vue 3 前端（4 个页面）
├── scripts/evaluate_rag.py  # RAG 离线评估脚本
├── tests/                   # 114 个后端测试
├── compose.yaml             # Qdrant Docker 编排
└── requirements.txt
```

## 相关链接

- 学习路线与冲刺计划：https://github.com/didilili/ai-agents-from-zero
