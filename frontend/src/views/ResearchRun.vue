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

async function loadTask() {
  try {
    const tasks = await listResearchTasks()
    task.value = tasks.find((t) => String(t.id) === taskId) || null

    if (!task.value) {
      error.value = "任务不存在"
      return
    }

    if (task.value.status === "awaiting_approval") {
      awaitingApproval.value = true
      try {
        plan.value = JSON.parse(task.value.plan)
      } catch {
        plan.value = null
      }
    }
  } catch (e) {
    error.value = e.message
  }
}

function pushEvent(event) {
  events.value.push(event)
  if (event.type === "awaiting_approval") {
    awaitingApproval.value = true
  }
  if (event.type === "completed") {
    router.push(`/research/report/${taskId}`)
  }
}

async function onApprove(approved) {
  running.value = true
  error.value = ""
  awaitingApproval.value = false
  try {
    await streamApprove(taskId, approved, pushEvent)
  } catch (e) {
    error.value = e.message
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
        {{ task.status }}
      </span>
    </div>

    <!-- 计划确认框 -->
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

    <!-- 进度事件流 -->
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
.error {
  color: #c62828;
}
</style>
