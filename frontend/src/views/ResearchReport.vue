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
.hint {
  color: #999;
}
.error {
  color: #c62828;
}
.error-box {
  background: #ffebee;
  border: 1px solid #ef9a9a;
  border-radius: 8px;
  padding: 16px;
  color: #c62828;
}
</style>
