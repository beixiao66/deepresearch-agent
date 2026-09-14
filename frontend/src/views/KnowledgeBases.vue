<script setup>
import { computed, onMounted, ref } from "vue"
import {
  listKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  listDocuments,
  uploadDocument,
  retryDocument,
  deleteDocument,
} from "../api"

import { showErrorDialog } from "../errorDialog"

const bases = ref([])
const selectedId = ref(null)
const documents = ref([])
const newName = ref("")
const newDesc = ref("")
const error = ref("")
const uploading = ref(false)
const uploadQueue = ref([])

const queueStatusLabel = {
  pending: "排队中",
  uploading: "上传中",
  done: "已完成",
  failed: "失败",
}

const uploadProgress = computed(() => ({
  done: uploadQueue.value.filter((item) => item.status === "done").length,
  failed: uploadQueue.value.filter((item) => item.status === "failed").length,
  total: uploadQueue.value.length,
}))

async function loadBases() {
  try {
    bases.value = await listKnowledgeBases()
  } catch (e) {
    error.value = e.message
  }
}

async function selectBase(id) {
  selectedId.value = id
  try {
    documents.value = await listDocuments(id)
  } catch (e) {
    error.value = e.message
  }
}

async function onDeleteKnowledgeBase(id) {
  if (!confirm("确定删除该知识库？其下所有文档、向量和索引将一并删除。")) return
  try {
    await deleteKnowledgeBase(id)
    if (selectedId.value === id) {
      selectedId.value = null
      documents.value = []
    }
    await loadBases()
  } catch (e) {
    error.value = e.message
  }
}

async function onCreateBase() {
  error.value = ""
  if (!newName.value.trim()) {
    error.value = "请输入知识库名称"
    showErrorDialog(error.value)
    return
  }
  try {
    const kb = await createKnowledgeBase(newName.value, newDesc.value)
    newName.value = ""
    newDesc.value = ""
    await loadBases()
    await selectBase(kb.id)
  } catch (e) {
    error.value = e.message
  }
}

async function onUpload(event) {
  const files = Array.from(event.target.files || [])
  // 立即清空 input，否则再次选择同一批文件不会触发 change
  event.target.value = ""

  const knowledgeBaseId = selectedId.value
  if (!files.length || knowledgeBaseId === null) return

  error.value = ""
  uploadQueue.value = files.map((file) => ({
    name: file.name,
    status: "pending",
    error: "",
  }))
  uploading.value = true

  for (const [index, file] of files.entries()) {
    const item = uploadQueue.value[index]
    item.status = "uploading"
    try {
      await uploadDocument(knowledgeBaseId, file, { silent: true })
      item.status = "done"
    } catch (e) {
      item.status = "failed"
      item.error = e.message
    }
  }

  uploading.value = false

  // 上传期间用户可能切到了别的知识库，列表只刷新原知识库
  if (selectedId.value !== knowledgeBaseId) return
  try {
    documents.value = await listDocuments(knowledgeBaseId)
  } catch (e) {
    error.value = e.message
  }
}

async function onRetry(documentId) {
  error.value = ""
  uploading.value = true
  try {
    await retryDocument(selectedId.value, documentId)
    documents.value = await listDocuments(selectedId.value)
  } catch (e) {
    error.value = e.message
    documents.value = await listDocuments(selectedId.value)
  } finally {
    uploading.value = false
  }
}

async function onDeleteDocument(documentId) {
  if (!confirm("确定删除该文档？")) return
  try {
    await deleteDocument(selectedId.value, documentId)
    documents.value = await listDocuments(selectedId.value)
  } catch (e) {
    error.value = e.message
  }
}

const statusLabel = {
  pending: "待处理",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
}

const selectedBase = computed(() =>
  bases.value.find((kb) => kb.id === selectedId.value)
)

onMounted(loadBases)
</script>

<template>
  <div class="kb-page">
    <header class="page-head">
      <span class="eyebrow">KNOWLEDGE BASE</span>
      <h2 class="page-title">知识库管理</h2>
      <p class="page-subtitle">
        上传文档自动完成解析、切分、向量化与索引，供深度研究检索使用
      </p>
    </header>

    <div class="row">
      <section class="panel">
        <h3 class="panel-title">知识库列表</h3>
        <ul class="kb-list">
          <li
            v-for="kb in bases"
            :key="kb.id"
            :class="{ active: kb.id === selectedId }"
            @click="selectBase(kb.id)"
          >
            <div class="kb-info">
              <strong>{{ kb.name }}</strong>
              <span class="kb-desc">{{ kb.description || "无描述" }}</span>
            </div>
            <button
              class="kb-delete danger"
              @click.stop="onDeleteKnowledgeBase(kb.id)"
            >
              删除
            </button>
          </li>
          <li v-if="!bases.length" class="kb-empty">
            还没有知识库，先在下方创建一个
          </li>
        </ul>

        <div class="create-form">
          <input
            v-model="newName"
            placeholder="知识库名称"
          />
          <input
            v-model="newDesc"
            placeholder="描述（可选）"
          />
          <button class="primary" @click="onCreateBase">创建知识库</button>
        </div>
      </section>

      <section class="panel">
        <h3 class="panel-title">
          文档
          <span v-if="selectedBase" class="panel-sub">
            {{ selectedBase.name }}
          </span>
        </h3>

        <div v-if="selectedId !== null" class="upload-row">
          <input
            type="file"
            multiple
            accept=".pdf,.md,.txt,.docx,.html,.htm,.xlsx,.pptx,.csv"
            :disabled="uploading"
            @change="onUpload"
          />
          <span class="hint">可一次选择多个文件，选中后依次上传</span>
        </div>

        <div v-if="uploadQueue.length" class="upload-queue">
          <div class="queue-head">
            <span>
              上传进度 {{ uploadProgress.done }}/{{ uploadProgress.total }}
              <template v-if="uploadProgress.failed">
                · 失败 {{ uploadProgress.failed }}
              </template>
            </span>
          </div>
          <ul>
            <li
              v-for="(item, index) in uploadQueue"
              :key="index"
              :class="item.status"
            >
              <span class="queue-name">{{ item.name }}</span>
              <span class="queue-status">
                {{ queueStatusLabel[item.status] }}
                <template v-if="item.error">：{{ item.error }}</template>
              </span>
            </li>
          </ul>
        </div>

        <table v-if="documents.length" class="data-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>状态</th>
              <th>大小</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in documents" :key="doc.id">
              <td class="doc-name">{{ doc.original_filename }}</td>
              <td>
                <span :class="['badge', doc.status]">
                  {{ statusLabel[doc.status] || doc.status }}
                </span>
              </td>
              <td class="doc-size">{{ (doc.file_size / 1024).toFixed(1) }} KB</td>
              <td>
                <div class="row-actions">
                  <button
                    v-if="doc.status === 'failed'"
                    @click="onRetry(doc.id)"
                    :disabled="uploading"
                  >
                    重试
                  </button>
                  <button
                    class="danger"
                    @click="onDeleteDocument(doc.id)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="selectedId !== null" class="hint">
          暂无文档，可上传 PDF / Markdown / TXT / Word / Excel / PPT / CSV / HTML
        </p>
        <p v-else class="hint">请从左侧选择一个知识库</p>
      </section>
    </div>

    <p v-if="error" class="error page-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: start;
}

.panel-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 14px;
}
.panel-sub {
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 400;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0 0 16px;
  padding: 0;
  list-style: none;
}
.kb-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.kb-list li:hover {
  background: var(--bg-elevated);
}
.kb-list li.active {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.kb-list li.kb-empty {
  cursor: default;
  color: var(--text-dim);
  font-size: 13px;
}
.kb-list li.kb-empty:hover {
  background: transparent;
}
.kb-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.kb-info strong {
  font-size: 13.5px;
  font-weight: 600;
}
.kb-desc {
  color: var(--text-dim);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-delete {
  flex-shrink: 0;
  padding: 3px 10px;
  font-size: 12px;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.upload-row input[type="file"] {
  max-width: 420px;
}
.upload-row .hint {
  font-size: 12px;
}

.upload-queue {
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-elevated);
}
.queue-head {
  margin-bottom: 8px;
  color: var(--text);
  font-size: 12.5px;
  font-family: var(--mono);
}
.upload-queue ul {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
  max-height: 220px;
  overflow-y: auto;
  list-style: none;
}
.upload-queue li {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12.5px;
}
.queue-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.queue-status {
  flex-shrink: 0;
  color: var(--text-dim);
  font-size: 11.5px;
}
.upload-queue li.uploading .queue-status {
  color: var(--info);
}
.upload-queue li.done .queue-status {
  color: var(--ok);
}
.upload-queue li.failed .queue-status {
  color: var(--danger);
  white-space: normal;
  text-align: right;
}
.upload-queue li.failed .queue-name {
  color: var(--danger);
}

.doc-name {
  overflow-wrap: anywhere;
}
.doc-size {
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: 12px;
  white-space: nowrap;
}
.row-actions {
  display: flex;
  gap: 8px;
}
.row-actions button {
  padding: 5px 12px;
  font-size: 12.5px;
}

.page-error {
  margin-top: 16px;
}

@media (max-width: 900px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
