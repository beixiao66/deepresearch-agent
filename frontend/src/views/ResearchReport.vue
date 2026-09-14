<script setup>
import { onMounted, ref, computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { marked } from "marked"
import { listResearchTasks } from "../api"

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const task = ref(null)
const error = ref("")

const statusLabel = {
  pending: "待处理",
  running: "执行中",
  awaiting_approval: "待确认",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
}

const reportHtml = computed(() => {
  if (!task.value || !task.value.report) return ""
  return marked.parse(task.value.report)
})

const tokenUsage = computed(() => {
  if (!task.value || !task.value.token_usage) return null
  try {
    return JSON.parse(task.value.token_usage)
  } catch {
    return null
  }
})

const tokenStages = computed(() => {
  const usage = tokenUsage.value
  if (!usage) return []
  const labels = {
    plan: "生成计划",
    next_queries: "补充查询",
    report: "生成报告",
  }
  return Object.entries(usage)
    .filter(([key]) => labels[key])
    .map(([key, value]) => ({
      key,
      label: labels[key],
      prompt: value.prompt_tokens || 0,
      completion: value.completion_tokens || 0,
      total: value.total_tokens || 0,
    }))
})

const tokenTotals = computed(() => {
  const stages = tokenStages.value
  if (!stages.length) return { prompt: 0, completion: 0, total: 0 }
  return {
    prompt: stages.reduce((sum, s) => sum + s.prompt, 0),
    completion: stages.reduce((sum, s) => sum + s.completion, 0),
    total: stages.reduce((sum, s) => sum + s.total, 0),
  }
})

function stageWidth(stage) {
  const total = tokenTotals.value.total
  if (!total) return 0
  return Math.max(3, Math.round((stage.total / total) * 100))
}

const citationSources = computed(() => {
  if (!task.value || !task.value.sources) return []
  try {
    return JSON.parse(task.value.sources)
  } catch {
    return []
  }
})

// 报告正文引用了 [n]，来源列表按 1 起编号与之一一对应
const numberedSources = computed(() =>
  citationSources.value.map((source, index) => ({
    number: index + 1,
    source,
  }))
)

// 研究是一次性任务，报告不能继续追问；带上主题跳到对话页继续
function continueInChat() {
  if (!task.value) return
  router.push({
    path: "/chat",
    query: { topic: task.value.topic },
  })
}

async function loadTask() {
  try {
    const tasks = await listResearchTasks()
    task.value =
      tasks.find((t) => String(t.id) === taskId) || null
    if (!task.value) {
      error.value = "任务不存在"
    }
  } catch (e) {
    error.value = e.message
  }
}

onMounted(loadTask)
</script>

<template>
  <div class="report-page">
    <header class="page-head">
      <span class="eyebrow">RESEARCH REPORT</span>
      <h2 class="page-title">研究报告</h2>
      <p v-if="task" class="page-subtitle">
        任务 #{{ task.id }} · 知识库 {{ task.knowledge_base_id }}
      </p>
    </header>

    <div v-if="task" class="meta">
      <strong class="meta-topic">{{ task.topic }}</strong>
      <span :class="['badge', task.status]">
        {{ statusLabel[task.status] || task.status }}
      </span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div
      v-if="task && task.report"
      class="follow-up"
    >
      <div class="follow-up-body">
        <strong>研究是一次性任务，不能就这份报告继续追问。</strong>
        <p>
          需要继续深挖，请带着问题到「对话」继续；
          <em>对话不检索知识库</em>，回答基于模型自身知识与对话历史、没有引用来源。
          需要新的、可追溯的依据，请重新发起一次研究。
        </p>
      </div>
      <button class="primary follow-up-btn" @click="continueInChat">
        带着主题去对话
      </button>
    </div>

    <div
      v-if="task && task.report"
      class="markdown"
      v-html="reportHtml"
    ></div>

    <div v-if="task && !task.report && task.status !== 'failed'">
      <p class="hint">报告尚未生成，请先到执行页确认计划。</p>
      <router-link class="inline-link" :to="`/research/run/${taskId}`">
        前往执行页
      </router-link>
    </div>

    <div v-if="task && task.status === 'cancelled'" class="panel state-box">
      <h3>研究已取消</h3>
      <p class="hint">{{ task.error_message || "用户已取消此次研究任务" }}</p>
    </div>

    <div v-if="task && task.status === 'failed'" class="panel state-box failed">
      <h3>研究失败</h3>
      <p class="hint">{{ task.error_message }}</p>
    </div>

    <section v-if="numberedSources.length" class="panel sources">
      <h3>参考来源（{{ numberedSources.length }}）</h3>
      <ul class="source-list">
        <li v-for="item in numberedSources" :key="item.number" class="source-item">
          <span class="source-number">[{{ item.number }}]</span>
          <div class="source-body">
            <div class="source-title">
              <template v-if="item.source.source_type === 'web'">
                <a
                  v-if="item.source.url"
                  :href="item.source.url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ item.source.url }}
                </a>
                <span v-else>网页来源</span>
              </template>
              <template v-else>
                {{ item.source.filename || `文档 ${item.source.document_id}` }}
                <span v-if="item.source.chunk_index !== null && item.source.chunk_index !== undefined">
                  · 片段 {{ item.source.chunk_index }}
                </span>
              </template>
            </div>
            <div class="source-score">相关度 {{ item.source.score.toFixed(3) }}</div>
            <div class="source-text">{{ item.source.text }}</div>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="tokenStages.length" class="panel token-usage">
      <h3>Token 消耗统计</h3>
      <div class="token-summary">
        <div class="token-total">
          <span class="token-num">{{ tokenTotals.total }}</span>
          <span class="token-label">总 Token</span>
        </div>
        <div class="token-total">
          <span class="token-num">{{ tokenTotals.prompt }}</span>
          <span class="token-label">输入 Token</span>
        </div>
        <div class="token-total">
          <span class="token-num">{{ tokenTotals.completion }}</span>
          <span class="token-label">输出 Token</span>
        </div>
      </div>
      <div class="token-bar">
        <div
          v-for="stage in tokenStages"
          :key="stage.key"
          class="token-segment"
          :class="`seg-${stage.key}`"
          :style="{ width: stageWidth(stage) + '%' }"
          :title="`${stage.label}：${stage.total} token`"
        ></div>
      </div>
      <div class="token-stages">
        <div
          v-for="stage in tokenStages"
          :key="stage.key"
          class="token-stage"
        >
          <span class="stage-dot" :class="`seg-${stage.key}`"></span>
          <span class="stage-label">{{ stage.label }}</span>
          <span class="stage-value">
            输入 {{ stage.prompt }} / 输出 {{ stage.completion }}
          </span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.meta-topic {
  font-size: 15px;
}

.follow-up {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
  padding: 14px 18px;
  border: 1px solid rgba(45, 212, 191, 0.25);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius);
  background: var(--accent-dim);
}
.follow-up-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
.follow-up-body strong {
  color: var(--text);
}
.follow-up-body p {
  color: var(--text-dim);
  font-size: 12.5px;
  line-height: 1.7;
}
.follow-up-body em {
  color: var(--text);
  font-style: normal;
  font-weight: 600;
}
.follow-up-btn {
  flex-shrink: 0;
}

.inline-link {
  display: inline-block;
  margin-top: 8px;
  font-size: 13px;
}

.state-box {
  margin-top: 16px;
}
.state-box h3 {
  margin-bottom: 6px;
}
.state-box.failed {
  border-color: rgba(248, 113, 113, 0.35);
}

.sources,
.token-usage {
  margin-top: 20px;
}
.sources h3,
.token-usage h3 {
  margin-bottom: 12px;
}

.source-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.source-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.source-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.source-number {
  flex-shrink: 0;
  color: var(--accent);
  font-family: var(--mono);
  font-size: 13px;
  font-weight: 700;
}
.source-body {
  min-width: 0;
}
.source-title {
  color: var(--text);
  font-size: 13.5px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.source-score {
  margin-top: 2px;
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 11.5px;
}
.source-text {
  display: -webkit-box;
  margin-top: 6px;
  overflow: hidden;
  color: var(--text-dim);
  font-size: 12.5px;
  line-height: 1.7;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.token-summary {
  display: flex;
  gap: 36px;
  margin-bottom: 14px;
}
.token-total {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.token-num {
  color: var(--accent);
  font-family: var(--mono);
  font-size: 20px;
  font-weight: 700;
}
.token-label {
  color: var(--text-dim);
  font-size: 11.5px;
}
.token-bar {
  display: flex;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
}
.token-segment {
  height: 100%;
  transition: width 0.3s ease;
}
.seg-plan {
  background: var(--accent);
}
.seg-next_queries {
  background: var(--info);
}
.seg-report {
  background: var(--warn);
}
.token-stages {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 14px;
}
.token-stage {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12.5px;
}
.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.stage-label {
  width: 64px;
  color: var(--text);
  font-weight: 600;
}
.stage-value {
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 12px;
}

@media (max-width: 720px) {
  .follow-up {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

<!-- markdown 内容由 marked 渲染后通过 v-html 插入，scoped 样式不生效，
     必须用非 scoped 样式块覆盖 -->
<style>
.markdown {
  padding: 24px 26px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-panel);
  color: var(--text);
  font-size: 14px;
  line-height: 1.8;
}
.markdown h1,
.markdown h2,
.markdown h3 {
  margin: 1.4em 0 0.6em;
  color: var(--text);
}
.markdown > :first-child {
  margin-top: 0;
}
.markdown h1 {
  font-size: 22px;
}
.markdown h2 {
  font-size: 18px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.markdown h3 {
  font-size: 15px;
}
.markdown p {
  margin: 0 0 12px;
}
.markdown ul,
.markdown ol {
  margin: 0 0 12px;
  padding-left: 22px;
}
.markdown li {
  margin: 4px 0;
}
.markdown code {
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--accent);
  font-family: var(--mono);
  font-size: 12.5px;
}
.markdown pre {
  margin: 0 0 12px;
  padding: 14px;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #0d1117;
}
.markdown pre code {
  padding: 0;
  background: none;
  color: var(--text);
}
.markdown table {
  width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
  font-size: 13px;
}
.markdown th,
.markdown td {
  padding: 8px 12px;
  text-align: left;
  border: 1px solid var(--border);
}
.markdown th {
  background: var(--bg-elevated);
  color: var(--text-dim);
  font-weight: 500;
}
.markdown blockquote {
  margin: 12px 0;
  padding: 4px 16px;
  border-left: 3px solid var(--accent);
  background: var(--accent-dim);
  color: var(--text-dim);
}
.markdown a {
  color: var(--accent);
}
.markdown hr {
  margin: 20px 0;
  border: none;
  border-top: 1px solid var(--border);
}
</style>
