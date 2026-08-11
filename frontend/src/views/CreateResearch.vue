<script setup>
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { listKnowledgeBases, streamResearch } from "../api"
import { showErrorDialog } from "../errorDialog"

const router = useRouter()

const bases = ref([])
const topic = ref("")
const knowledgeBaseId = ref(null)
const useWebSearch = ref(false)
const running = ref(false)
const error = ref("")
const taskId = ref(null)
const plan = ref(null)

onMounted(async () => {
  try {
    bases.value = await listKnowledgeBases()
    if (bases.value.length) {
      knowledgeBaseId.value = bases.value[0].id
    }
  } catch (e) {
    error.value = e.message
  }
})

async function onCreate() {
  error.value = ""
  if (!topic.value.trim()) {
    error.value = "请输入研究主题"
    showErrorDialog(error.value)
    return
  }
  if (knowledgeBaseId.value === null) {
    error.value = "请选择知识库"
    showErrorDialog(error.value)
    return
  }

  running.value = true
  try {
    let receivedPlan = null

    await streamResearch(
      {
        topic: topic.value,
        knowledge_base_id: knowledgeBaseId.value,
        use_web_search: useWebSearch.value,
      },
      (event) => {
        if (event.type === "task_created") {
          taskId.value = event.task_id
        }
        if (event.type === "awaiting_approval") {
          receivedPlan = true
        }
      }
    )

    // 到暂停点：跳转执行页做计划确认
    if (taskId.value) {
      router.push(`/research/run/${taskId.value}`)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    running.value = false
  }
}
</script>

<template>
  <div class="create-page">
    <h2>创建研究</h2>

    <div class="form">
      <label>研究主题</label>
      <textarea
        v-model="topic"
        rows="3"
        placeholder="例如：什么是 RAG？它在企业知识库中的应用"
      ></textarea>

      <label>检索知识库</label>
      <select v-model="knowledgeBaseId">
        <option
          v-for="kb in bases"
          :key="kb.id"
          :value="kb.id"
        >
          {{ kb.name }}
        </option>
      </select>

      <label class="check-row">
        <input type="checkbox" v-model="useWebSearch" />
        知识库不足时允许联网搜索
      </label>

      <button
        class="primary"
        :disabled="running"
        @click="onCreate"
      >
        {{ running ? "正在生成研究计划..." : "开始研究" }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.form {
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
label {
  font-weight: 600;
  font-size: 14px;
}
textarea,
select {
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 14px;
}
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 400;
}
.primary {
  padding: 12px;
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  cursor: pointer;
}
.primary:disabled {
  opacity: 0.6;
}
.error {
  color: #c62828;
}
</style>
