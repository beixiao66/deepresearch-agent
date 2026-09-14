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
const file = ref(null)
const running = ref(false)
const error = ref("")
const taskId = ref(null)

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

function onFileSelected(event) {
  const selected = event.target.files[0]
  file.value = selected || null
  // 选了文件后，知识库变为可选（不强制）
}

async function onCreate() {
  error.value = ""
  if (!topic.value.trim()) {
    error.value = "请输入研究主题"
    showErrorDialog(error.value)
    return
  }
  if (!file.value && knowledgeBaseId.value === null) {
    error.value = "请选择知识库或上传文件"
    showErrorDialog(error.value)
    return
  }

  running.value = true
  try {
    await streamResearch(
      {
        topic: topic.value,
        knowledge_base_id: knowledgeBaseId.value,
        use_web_search: useWebSearch.value,
        file: file.value,
      },
      (event) => {
        if (event.type === "task_created") {
          taskId.value = event.task_id
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
    <header class="page-head">
      <span class="eyebrow">NEW RESEARCH</span>
      <h2 class="page-title">创建研究</h2>
      <p class="page-subtitle">
        检索知识库 → 生成计划 → 确认后并行研究 → 输出带引用的报告
      </p>
    </header>

    <section class="panel form">
      <div class="field">
        <label for="topic">研究主题</label>
        <textarea
          id="topic"
          v-model="topic"
          rows="3"
          placeholder="例如：什么是 RAG？它在企业知识库中的应用"
        ></textarea>
      </div>

      <div class="field">
        <label for="kb">检索知识库</label>
        <select id="kb" v-model="knowledgeBaseId">
          <option
            v-for="kb in bases"
            :key="kb.id"
            :value="kb.id"
          >
            {{ kb.name }}
          </option>
        </select>
        <p v-if="!bases.length" class="hint">
          还没有知识库，可先在「知识库」页创建
        </p>
      </div>

      <label class="check-row">
        <input type="checkbox" v-model="useWebSearch" />
        <span>知识库不足时允许联网搜索（Tavily）</span>
      </label>

      <div class="field">
        <label for="file">或上传文件直接研究</label>
        <input
          id="file"
          type="file"
          accept=".pdf,.md,.txt,.docx,.html,.htm,.xlsx,.pptx,.csv"
          @change="onFileSelected"
        />
        <p v-if="file" class="hint">
          已选择：{{ file.name }}（自动创建临时知识库，研究完成后删除）
        </p>
      </div>

      <button
        class="primary submit"
        :disabled="running"
        @click="onCreate"
      >
        {{ running ? "正在生成研究计划..." : "开始研究" }}
      </button>

      <p class="hint note">
        研究是一次性任务，报告生成后不能继续追问；需要追问请到「对话」页。
      </p>

      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </div>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 620px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field label {
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
}
.field .hint {
  font-size: 12px;
}

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}

.submit {
  margin-top: 4px;
  padding: 12px;
  font-size: 14px;
}

.note {
  font-size: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
</style>
