<script setup>
import { onMounted, ref } from "vue"
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
  error.value = ""
  const file = event.target.files[0]
  if (!file || selectedId.value === null) return

  uploading.value = true
  try {
    await uploadDocument(selectedId.value, file)
    documents.value = await listDocuments(selectedId.value)
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
    event.target.value = ""
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

onMounted(loadBases)
</script>

<template>
  <div class="kb-page">
    <h2>知识库管理</h2>

    <div class="row">
      <div class="panel">
        <h3>知识库列表</h3>
        <ul class="kb-list">
          <li
            v-for="kb in bases"
            :key="kb.id"
            :class="{ active: kb.id === selectedId }"
            @click="selectBase(kb.id)"
          >
            <div class="kb-info">
              <strong>{{ kb.name }}</strong>
              <span class="kb-desc">{{ kb.description }}</span>
            </div>
            <button
              class="kb-delete"
              @click.stop="onDeleteKnowledgeBase(kb.id)"
            >
              删除
            </button>
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
          <button @click="onCreateBase">创建</button>
        </div>
      </div>

      <div class="panel">
        <h3>
          文档
          <template v-if="selectedId !== null">
            （知识库 {{ selectedId }}）
          </template>
        </h3>

        <div v-if="selectedId !== null" class="upload-row">
          <input
            type="file"
            accept=".pdf,.md,.txt,.docx,.html,.htm,.xlsx,.pptx,.csv"
            @change="onUpload"
          />
          <span v-if="uploading">上传中...</span>
        </div>

        <table v-if="documents.length" class="doc-table">
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
              <td>{{ doc.original_filename }}</td>
              <td>
                <span
                  :class="['badge', doc.status]"
                >
                  {{ statusLabel[doc.status] || doc.status }}
                </span>
              </td>
              <td>{{ (doc.file_size / 1024).toFixed(1) }} KB</td>
              <td>
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
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else-if="selectedId !== null" class="hint">
          暂无文档，上传 PDF/Markdown/TXT/Word/Excel/PPT/CSV/HTML 文件
        </p>
        <p v-else class="hint">请选择左侧知识库</p>

      </div>
    </div>
  </div>
</template>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 24px;
}
.panel {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
}
.kb-list {
  list-style: none;
  padding: 0;
  margin: 0 0 16px;
}
.kb-list li {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.kb-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.kb-list li:hover {
  background: #f0f4ff;
}
.kb-list li.active {
  background: #e3f2fd;
}
.kb-desc {
  font-size: 12px;
  color: #777;
}
.kb-delete {
  flex-shrink: 0;
  padding: 2px 10px;
  font-size: 12px;
  background: #d32f2f;
}
.create-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.create-form input {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.upload-row {
  margin-bottom: 12px;
}
.doc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.doc-table th,
.doc-table td {
  text-align: left;
  padding: 8px;
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
.badge.processing {
  background: #fff3e0;
  color: #e65100;
}
.badge.failed {
  background: #ffebee;
  color: #c62828;
}
.badge.pending {
  background: #eceff1;
  color: #546e7a;
}
button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  background: #1976d2;
  color: #fff;
  cursor: pointer;
}
button.danger {
  background: #d32f2f;
}
.doc-table td button + button {
  margin-left: 8px;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.hint {
  color: #999;
}
</style>
