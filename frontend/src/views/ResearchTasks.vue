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
    <header class="page-head">
      <span class="eyebrow">RESEARCH HISTORY</span>
      <h2 class="page-title">研究历史</h2>
      <p class="page-subtitle">所有研究任务、状态与报告入口</p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="tasks.length" class="panel table-panel">
      <table class="data-table">
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
            <td class="task-id">#{{ task.id }}</td>
            <td class="task-topic">{{ task.topic }}</td>
            <td class="task-kb">{{ task.knowledge_base_id }}</td>
            <td>
              <span :class="['badge', task.status]">
                {{ statusLabel[task.status] || task.status }}
              </span>
            </td>
            <td>
              <router-link
                v-if="task.status === 'awaiting_approval'"
                class="row-link"
                :to="`/research/run/${task.id}`"
              >
                去确认
              </router-link>
              <router-link
                v-else-if="task.status === 'completed'"
                class="row-link"
                :to="`/research/report/${task.id}`"
              >
                看报告
              </router-link>
              <span v-else class="task-none">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-else-if="!error" class="panel empty-state">
      <p class="hint">暂无研究任务</p>
      <router-link class="row-link" to="/research/create">
        去创建第一个研究
      </router-link>
    </section>
  </div>
</template>

<style scoped>
.table-panel {
  padding: 6px 8px;
}
.task-id {
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 12px;
  white-space: nowrap;
}
.task-topic {
  overflow-wrap: anywhere;
}
.task-kb {
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 12px;
}
.task-none {
  color: var(--text-dim);
}
.row-link {
  display: inline-block;
  padding: 4px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  background: var(--bg-elevated);
  font-size: 12.5px;
  text-decoration: none;
  transition: border-color 0.15s;
}
.row-link:hover {
  border-color: var(--accent);
  text-decoration: none;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
</style>
