<script setup>
import { onMounted, ref, computed } from "vue"
import { useRoute } from "vue-router"
import { marked } from "marked"
import { listResearchTasks } from "../api"

const route = useRoute()
const taskId = route.params.taskId

const task = ref(null)
const error = ref("")

const reportHtml = computed(() => {
  if (!task.value || !task.value.report) return ""
  return marked.parse(task.value.report)
})

const webSources = computed(() => {
  if (!task.value || !task.value.plan) return []
  try {
    const plan = JSON.parse(task.value.plan)
    return plan.search_queries || []
  } catch {
    return []
  }
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
    <h2>研究报告</h2>

    <div v-if="task" class="meta">
      <strong>{{ task.topic }}</strong>
      <span :class="['badge', task.status]">
        {{ task.status }}
      </span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div
      v-if="task && task.report"
      class="markdown"
      v-html="reportHtml"
    ></div>

    <div v-if="task && !task.report && task.status !== 'failed'">
      <p class="hint">报告尚未生成，请先到执行页确认计划。</p>
      <router-link :to="`/research/run/${taskId}`">
        前往执行页
      </router-link>
    </div>

    <div v-if="task && task.status === 'cancelled'" class="cancelled-box">
      <h3>研究已取消</h3>
      <p>{{ task.error_message || "用户已取消此次研究任务" }}</p>
    </div>

    <div v-if="task && task.status === 'failed'" class="error-box">
      <h3>研究失败</h3>
      <p>{{ task.error_message }}</p>
    </div>

    <div v-if="webSources.length" class="sources">
      <h3>检索关键词</h3>
      <ul>
        <li v-for="(q, i) in webSources" :key="i">{{ q }}</li>
      </ul>
    </div>

    <div v-if="tokenStages.length" class="token-usage">
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
    </div>
  </div>
</template>

<style scoped>
.meta {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}
.badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  background: #eceff1;
  color: #546e7a;
}
.markdown {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 24px;
  line-height: 1.7;
}
.markdown h1,
.markdown h2,
.markdown h3 {
  margin-top: 1.2em;
}
.markdown pre {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}
.sources {
  margin-top: 24px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
}
.token-usage {
  margin-top: 24px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
}
.token-usage h3 {
  margin-top: 0;
}
.token-summary {
  display: flex;
  gap: 32px;
  margin-bottom: 12px;
}
.token-total {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.token-num {
  font-size: 22px;
  font-weight: 700;
  color: #1976d2;
}
.token-label {
  font-size: 12px;
  color: #777;
}
.token-bar {
  display: flex;
  height: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: #f0f0f0;
}
.token-segment {
  height: 100%;
  transition: width 0.3s ease;
}
.seg-plan {
  background: #1976d2;
}
.seg-next_queries {
  background: #7c4dff;
}
.seg-report {
  background: #e65100;
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
  gap: 8px;
  font-size: 13px;
}
.stage-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.stage-label {
  font-weight: 600;
  color: #333;
  width: 64px;
}
.stage-value {
  color: #777;
}
.hint {
  color: #999;
}
.error {
  color: #c62828;
}
.cancelled-box {
  background: #f5f5f5;
  border: 1px solid #bdbdbd;
  border-radius: 8px;
  padding: 16px;
  color: #424242;
}
.error-box {
  background: #ffebee;
  border: 1px solid #ef9a9a;
  border-radius: 8px;
  padding: 16px;
  color: #c62828;
}
</style>
