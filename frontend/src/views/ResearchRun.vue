<script setup>
import { onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { streamApprove, listResearchTasks } from "../api"

const route = useRoute()

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
      review: 35,
      retrieve: 55,
      report: 85,
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
      progress.value = 35
    } else if (event.message.includes("检索知识库")) {
      progress.value = 55
    } else if (event.message.includes("联网搜索")) {
      progress.value = 65
    } else if (event.message.includes("生成研究报告")) {
      progress.value = 85
    }
  }

  if (event.type === "task_created") {
    progress.value = Math.max(progress.value, 10)
  }
  if (event.type === "awaiting_approval") {
    currentStage.value = 2
    progress.value = 35
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
  if (event.type === "completed") {
    task.value.status = "completed"
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
      progress.value = 35
      currentMessage.value = "研究计划已生成，等待确认"
      try {
        plan.value = JSON.parse(task.value.plan)
      } catch {
        plan.value = null
      }
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
  progress.value = approved ? 55 : 0
  currentMessage.value = approved ? "正在检索资料..." : "正在处理拒绝操作..."
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
    <h2>研究执行</h2>

    <div v-if="task" class="status-line">
      任务 #{{ task.id }}：{{ task.topic }}
      <span :class="['badge', task.status]">
        {{ task.status === 'awaiting_approval' ? '待确认' : task.status }}
      </span>
    </div>

    <div class="progress-panel">
      <div class="progress-header">
        <strong>{{ currentMessage }}</strong>
        <span>{{ progress }}%</span>
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
    </div>

    <div v-if="awaitingApproval && plan" class="plan-box">
      <h3>研究计划确认</h3>
      <p class="objective">{{ plan.objective }}</p>

      <h4>子问题</h4>
      <ul>
        <li v-for="(q, i) in plan.sub_questions" :key="i">
          {{ q }}
        </li>
      </ul>

      <h4>检索关键词</h4>
      <ul>
        <li v-for="(q, i) in plan.search_queries" :key="i">
          {{ q }}
        </li>
      </ul>

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
    </div>

    <div class="events">
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
          研究完成！
        </span>
        <span v-else>
          {{ event.message || event.type }}
        </span>
      </div>
    </div>

    <p v-if="completed" class="report-link">
      研究已完成，
      <router-link :to="`/research/report/${taskId}`">
        查看研究报告
      </router-link>
    </p>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.status-line {
  margin-bottom: 16px;
  font-size: 15px;
}
.badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  background: #eceff1;
  color: #546e7a;
}
.progress-panel {
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
  color: #333;
}
.progress-track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5e7eb;
}
.progress-bar {
  height: 100%;
  border-radius: inherit;
  background: #1976d2;
  transition: width 0.4s ease;
}
.progress-bar.failed {
  background: #d32f2f;
}
.progress-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 14px;
}
.progress-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: #9e9e9e;
  font-size: 12px;
}
.progress-step.active,
.progress-step.done {
  color: #1976d2;
  font-weight: 600;
}
.step-dot {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e5e7eb;
}
.progress-step.active .step-dot,
.progress-step.done .step-dot {
  background: #1976d2;
  color: #fff;
}
.plan-box {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.plan-box h3 {
  margin-top: 0;
}
.objective {
  color: #555;
}
.actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}
.primary {
  padding: 10px 20px;
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.danger {
  padding: 10px 20px;
  background: #d32f2f;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.primary:disabled,
.danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.events {
  background: #1a1a2e;
  color: #4fc3f7;
  border-radius: 8px;
  padding: 16px;
  font-family: monospace;
  font-size: 13px;
}
.event {
  padding: 4px 0;
}
.event-dot {
  margin-right: 8px;
  color: #4caf50;
}
.report-link {
  margin-top: 16px;
  color: #2e7d32;
}
.report-link a {
  color: #1976d2;
  font-weight: 600;
}
.error {
  color: #c62828;
}
</style>
