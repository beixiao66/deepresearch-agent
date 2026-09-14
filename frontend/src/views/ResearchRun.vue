<script setup>
import { onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { streamApprove, listResearchTasks } from "../api"

const route = useRoute()
const router = useRouter()

const taskId = route.params.taskId
const task = ref(null)
const events = ref([])
const awaitingApproval = ref(false)
const plan = ref(null)
const running = ref(false)
const error = ref("")
const currentMessage = ref("正在加载研究任务...")
const progress = ref(0)
const currentStage = ref(0)
const completed = ref(false)

const statusLabel = {
  pending: "待处理",
  running: "执行中",
  awaiting_approval: "待确认",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
}

const progressSteps = [
  { key: "plan", label: "生成计划", stage: 1 },
  { key: "review", label: "人工确认", stage: 2 },
  { key: "retrieve", label: "检索资料", stage: 3 },
  { key: "report", label: "生成报告", stage: 4 },
]

function updateProgress(event) {
  if (event.message) {
    currentMessage.value = event.message
  }

  if (event.type === "status") {
    const stageProgress = {
      plan: 25,
      review: 50,
      retrieve: 75,
      report: 90,
    }
    if (event.stage && stageProgress[event.stage]) {
      const stageIndex = {
        plan: 1,
        review: 2,
        retrieve: 3,
        report: 4,
      }
      currentStage.value = Math.max(
        currentStage.value,
        stageIndex[event.stage]
      )
      progress.value = Math.max(
        progress.value,
        stageProgress[event.stage]
      )
      return
    }

    if (event.message.includes("生成研究计划")) {
      progress.value = 25
    } else if (event.message.includes("研究计划已生成")) {
      progress.value = 50
    } else if (event.message.includes("检索知识库")) {
      progress.value = 75
    } else if (event.message.includes("联网搜索")) {
      progress.value = 75
    } else if (event.message.includes("生成研究报告")) {
      progress.value = 90
    }
  }

  if (event.type === "task_created") {
    progress.value = Math.max(progress.value, 10)
  }
  if (event.type === "awaiting_approval") {
    currentStage.value = 2
    progress.value = 50
  }
  if (event.type === "cancelled") {
    currentStage.value = 0
    progress.value = 0
    completed.value = false
    currentMessage.value = event.message || "用户已取消此次研究任务"
  }
  if (event.type === "completed") {
    currentStage.value = 4
    completed.value = true
    progress.value = 100
    currentMessage.value = "研究已完成"
  }
  if (event.type === "error") {
    currentMessage.value = event.message || "研究执行失败"
  }
}

function pushEvent(event) {
  events.value.push(event)
  updateProgress(event)
  if (event.type === "status") {
    if (event.stage === "report") {
      currentStage.value = 4
    } else if (event.stage === "retrieve") {
      currentStage.value = 3
    }
    task.value.status = "running"
  }
  if (event.type === "awaiting_approval") {
    task.value.status = "awaiting_approval"
    awaitingApproval.value = true
  }
  if (event.type === "cancelled") {
    task.value.status = "cancelled"
    awaitingApproval.value = false
    error.value = ""
  }
  if (event.type === "completed") {
    task.value.status = "completed"
    router.push(`/research/report/${taskId}`)
  }
  if (event.type === "error") {
    task.value.status = "failed"
  }
}

async function loadTask() {
  try {
    const tasks = await listResearchTasks()
    task.value = tasks.find((t) => String(t.id) === taskId) || null

    if (!task.value) {
      error.value = "任务不存在"
      currentMessage.value = "任务不存在"
      return
    }

    if (task.value.status === "awaiting_approval") {
      awaitingApproval.value = true
      currentStage.value = 2
      progress.value = 50
      currentMessage.value = "研究计划已生成，等待确认"
      try {
        plan.value = JSON.parse(task.value.plan)
      } catch {
        plan.value = null
      }
    } else if (task.value.status === "cancelled") {
      awaitingApproval.value = false
      currentStage.value = 0
      progress.value = 0
      currentMessage.value = task.value.error_message || "用户已取消此次研究任务"
    } else if (task.value.status === "completed") {
      currentStage.value = 4
      completed.value = true
      progress.value = 100
      currentMessage.value = "研究已完成"
    } else if (task.value.status === "failed") {
      currentMessage.value = task.value.error_message || "研究执行失败"
    }
  } catch (e) {
    error.value = e.message
    currentMessage.value = e.message
  }
}

async function onApprove(approved) {
  running.value = true
  error.value = ""
  awaitingApproval.value = false
  currentStage.value = approved ? 3 : 0
  progress.value = approved ? 75 : 0
  currentMessage.value = approved ? "正在检索资料..." : "正在取消研究任务..."
  if (approved && task.value) {
    task.value.status = "running"
  }
  try {
    await streamApprove(taskId, approved, pushEvent)
    if (approved && task.value) {
      task.value.status = "completed"
    }
  } catch (e) {
    error.value = e.message
    currentMessage.value = e.message
  } finally {
    running.value = false
  }
}

onMounted(loadTask)
</script>

<template>
  <div class="run-page">
    <header class="page-head">
      <span class="eyebrow">RESEARCH RUN</span>
      <h2 class="page-title">研究执行</h2>
      <p v-if="task" class="page-subtitle">
        任务 #{{ task.id }} · {{ task.topic }}
      </p>
    </header>

    <div v-if="task" class="status-line">
      <span :class="['badge', task.status]">
        {{ statusLabel[task.status] || task.status }}
      </span>
    </div>

    <section class="panel progress-panel">
      <div class="progress-header">
        <strong>{{ currentMessage }}</strong>
        <span class="progress-value">{{ progress }}%</span>
      </div>
      <div class="progress-track">
        <div
          class="progress-bar"
          :class="{ failed: currentMessage.includes('失败') }"
          :style="{ width: `${progress}%` }"
        ></div>
      </div>
      <div class="progress-steps">
        <div
          v-for="(step, index) in progressSteps"
          :key="step.key"
          :class="[
            'progress-step',
            {
              active: currentStage === step.stage,
              done: currentStage > step.stage || completed,
            },
          ]"
        >
          <span class="step-dot">{{ index + 1 }}</span>
          <span>{{ step.label }}</span>
        </div>
      </div>
    </section>

    <section v-if="awaitingApproval && plan" class="panel plan-box">
      <h3>研究计划确认</h3>
      <p class="objective">{{ plan.objective }}</p>

      <div class="plan-grid">
        <div>
          <h4>子问题</h4>
          <ul class="plan-list">
            <li v-for="(q, i) in plan.sub_questions" :key="i">
              {{ q }}
            </li>
          </ul>
        </div>
        <div>
          <h4>检索关键词</h4>
          <ul class="plan-list tags">
            <li v-for="(q, i) in plan.search_queries" :key="i">
              {{ q }}
            </li>
          </ul>
        </div>
      </div>

      <div class="actions">
        <button
          class="primary"
          :disabled="running"
          @click="onApprove(true)"
        >
          {{ running ? "执行中..." : "确认并开始研究" }}
        </button>
        <button
          class="danger"
          :disabled="running"
          @click="onApprove(false)"
        >
          拒绝
        </button>
      </div>
    </section>

    <section class="events">
      <div class="events-head">
        <span class="eyebrow">PROGRESS STREAM</span>
      </div>
      <div
        v-for="(event, i) in events"
        :key="i"
        class="event"
      >
        <span class="event-dot">●</span>
        <span v-if="event.type === 'status'">
          {{ event.message }}
        </span>
        <span v-else-if="event.type === 'task_created'">
          任务已创建（#{{ event.task_id }}）
        </span>
        <span v-else-if="event.type === 'completed'">
          研究完成，正在跳转报告页...
        </span>
        <span v-else>
          {{ event.message || event.type }}
        </span>
      </div>
      <div v-if="!events.length" class="event empty">
        <span>等待进度事件...</span>
      </div>
    </section>

    <p v-if="error" class="error page-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.status-line {
  margin-bottom: 14px;
}

.progress-panel {
  margin-bottom: 16px;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 13.5px;
}
.progress-value {
  color: var(--accent);
  font-family: var(--mono);
}
.progress-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
}
.progress-bar {
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width 0.4s ease;
}
.progress-bar.failed {
  background: var(--danger);
}
.progress-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 16px;
}
.progress-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--text-dim);
  font-size: 12px;
}
.progress-step.active,
.progress-step.done {
  color: var(--accent);
}
.step-dot {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--bg-elevated);
  font-family: var(--mono);
  font-size: 11px;
}
.progress-step.active .step-dot,
.progress-step.done .step-dot {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--accent-text);
  font-weight: 700;
}

.plan-box {
  margin-bottom: 16px;
}
.plan-box h3 {
  margin-bottom: 8px;
}
.objective {
  color: var(--text-dim);
  font-size: 13.5px;
}
.plan-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin: 16px 0 4px;
}
.plan-grid h4 {
  margin-bottom: 8px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-family: var(--mono);
  font-size: 11px;
}
.plan-list {
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.8;
}
.plan-list.tags {
  padding-left: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.plan-list.tags li {
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-elevated);
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
}
.actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.events {
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #0d1117;
  font-family: var(--mono);
  font-size: 12.5px;
  line-height: 1.9;
  color: var(--text-dim);
}
.events-head {
  margin-bottom: 8px;
}
.event {
  display: flex;
  gap: 8px;
  overflow-wrap: anywhere;
}
.event-dot {
  flex-shrink: 0;
  width: 5px;
  height: 5px;
  margin-top: 9px;
  border-radius: 50%;
  background: var(--accent);
  font-size: 0;
}
.event.empty {
  color: rgba(154, 163, 178, 0.6);
}

.page-error {
  margin-top: 16px;
}

@media (max-width: 900px) {
  .plan-grid {
    grid-template-columns: 1fr;
  }
}
</style>
