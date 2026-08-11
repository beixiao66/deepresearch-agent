<script setup>
import { onMounted, ref } from "vue"
import { listResearchTasks } from "../api"

const tasks = ref([])
const error = ref("")

const statusLabel = {
  pending: "待处理",
  running: "执行中",
  awaiting_approval: "待确认",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
}

onMounted(async () => {
  try {
    tasks.value = await listResearchTasks()
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="tasks-page">
    <h2>研究历史</h2>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="!tasks.length && !error" class="hint">
      暂无研究任务
    </p>

    <table v-if="tasks.length" class="task-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>主题</th>
          <th>知识库</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.id">
          <td>{{ task.id }}</td>
          <td>{{ task.topic }}</td>
          <td>{{ task.knowledge_base_id }}</td>
          <td>
            <span :class="['badge', task.status]">
              {{ statusLabel[task.status] || task.status }}
            </span>
          </td>
          <td>
            <router-link
              v-if="task.status === 'awaiting_approval'"
              :to="`/research/run/${task.id}`"
            >
              去确认
            </router-link>
            <router-link
              v-else-if="task.status === 'completed'"
              :to="`/research/report/${task.id}`"
            >
              看报告
            </router-link>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.task-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
}
.task-table th,
.task-table td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}
.badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.badge.completed {
  background: #e8f5e9;
  color: #2e7d32;
}
.badge.cancelled {
  background: #f5f5f5;
  color: #616161;
}
.badge.failed {
  background: #ffebee;
  color: #c62828;
}
.badge.awaiting_approval {
  background: #fff3e0;
  color: #e65100;
}
.badge.running {
  background: #e3f2fd;
  color: #1565c0;
}
.hint {
  color: #999;
}
.error {
  color: #c62828;
}
</style>
