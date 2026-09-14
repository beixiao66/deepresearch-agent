<script setup>
import { nextTick, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { marked } from "marked"
import {
  chatMessage,
  deleteConversation,
  getConversationMessages,
  listConversations,
} from "../api"

const route = useRoute()

const conversations = ref([])
const currentId = ref(localStorage.getItem("chat_conversation_id") || null)
const messages = ref([])
const draft = ref("")
const sending = ref(false)
const messagesRef = ref(null)

function renderMarkdown(content) {
  return marked.parse(content || "")
}

async function loadConversations() {
  conversations.value = await listConversations()
}

async function loadMessages(conversationId) {
  const data = await getConversationMessages(conversationId)
  messages.value = data.messages
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

async function switchConversation(conversationId) {
  currentId.value = conversationId
  localStorage.setItem("chat_conversation_id", conversationId)
  try {
    await loadMessages(conversationId)
  } catch {
    // 加载失败：api.js 全局对话框已提示，保持已切换的列表
  }
}

function newChat() {
  currentId.value = null
  localStorage.removeItem("chat_conversation_id")
  messages.value = []
  draft.value = ""
}

async function removeConversation(conversationId) {
  if (!confirm("确定删除该会话？对话记录将一并删除，不可恢复。")) return

  try {
    await deleteConversation(conversationId)
  } catch {
    // 删除失败：api.js 全局对话框已提示，保持列表不动
    return
  }

  // 删的是当前会话：回到空白新会话（同时清掉 localStorage 里的 id）
  if (currentId.value === conversationId) {
    newChat()
  }

  try {
    await loadConversations()
  } catch {
    // 列表刷新失败：全局对话框已提示
  }
}

async function send() {
  const question = draft.value.trim()
  if (!question || sending.value) return

  sending.value = true
  const targetId = currentId.value
  try {
    const result = await chatMessage(question, targetId)
    draft.value = ""
    if (currentId.value !== targetId) {
      // 请求期间已切换到其他会话：结果归属原会话（服务端已提交），
      // 不污染当前列表；切回原会话时可从服务端恢复
      return
    }
    messages.value.push({ role: "user", content: question })
    messages.value.push({ role: "assistant", content: result.answer })

    if (!targetId || result.conversation_id !== targetId) {
      currentId.value = result.conversation_id
      localStorage.setItem("chat_conversation_id", result.conversation_id)
    }
    await loadConversations()
    scrollToBottom()
  } catch {
    // 发送失败：api.js 全局对话框已提示，保留输入内容供重试
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  // 从研究报告页「带着主题去对话」进来：开一个新会话并预填问题
  // （对话读不到报告内容，只带主题过来，避免污染正在进行的会话）
  if (route.query.topic) {
    newChat()
    draft.value = String(route.query.topic)
  }

  try {
    await loadConversations()
  } catch {
    // 后端不可用：全局对话框已提示，保持空列表
    return
  }
  if (currentId.value) {
    try {
      await loadMessages(currentId.value)
    } catch {
      // 会话已被清理等情况：回到空会话
      currentId.value = null
      localStorage.removeItem("chat_conversation_id")
    }
  }
})
</script>

<template>
  <div class="chat-layout">
    <aside class="chat-sidebar">
      <button class="new-chat-btn" @click="newChat">
        ＋ 新建会话
      </button>
      <div class="conv-list">
        <div
          v-for="conversation in conversations"
          :key="conversation.id"
          class="conv-item"
          :class="{ active: conversation.id === currentId }"
          @click="switchConversation(conversation.id)"
        >
          <div class="conv-text">
            <span class="conv-title">{{ conversation.title }}</span>
            <span class="conv-time">
              {{ new Date(conversation.updated_at).toLocaleDateString() }}
            </span>
          </div>
          <button
            class="conv-delete"
            type="button"
            title="删除会话"
            aria-label="删除会话"
            @click.stop="removeConversation(conversation.id)"
          >
            ×
          </button>
        </div>
      </div>
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <span class="eyebrow">CHAT WORKSPACE</span>
        <h2 class="chat-title">DeepResearch 对话</h2>
        <p class="chat-subtitle">
          多轮对话记忆 · 不检索知识库
        </p>
      </header>

      <div ref="messagesRef" class="messages">
        <div v-if="messages.length === 0" class="empty">
          新建会话开始提问，或从左侧选择历史会话继续
        </div>
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message"
          :class="message.role"
        >
          <div
            v-if="message.role === 'assistant'"
            class="bubble markdown"
            v-html="renderMarkdown(message.content)"
          ></div>
          <div v-else class="bubble">{{ message.content }}</div>
        </div>
      </div>

      <p class="kb-notice">
        <span class="notice-mark">!</span>
        <span>
          对话<strong>不检索知识库</strong>：回答基于模型自身知识与对话历史，
          <strong>没有引用来源</strong>，可能与知识库资料不一致。
          需要可追溯的依据与引用，请使用
          <router-link to="/research/create">创建研究</router-link>。
        </span>
      </p>

      <form class="input-bar" @submit.prevent="send">
        <input
          v-model="draft"
          class="chat-input"
          placeholder="向 DeepResearch Agent 提问..."
        />
        <button
          type="submit"
          class="send-btn"
          :disabled="sending || !draft.trim()"
        >
          {{ sending ? "…" : "发送" }}
        </button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  /* 关键：行高必须受容器约束（minmax(0, 1fr)）。默认 auto 行会被消息
     内容撑高，.messages 就拿不到有界高度，flex:1 + overflow-y:auto 不生效，
     超出的部分再被 overflow:hidden 裁掉——表现为消息滚不动、输入框消失 */
  grid-template-rows: minmax(0, 1fr);
  height: calc(100vh - var(--shell-offset));
  min-height: 380px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0; /* grid 子项默认 min-height:auto，不置 0 会话列表撑高后无法内部滚动 */
  padding: 16px;
  border-right: 1px solid var(--border);
  background: var(--bg-panel);
}

.new-chat-btn {
  padding: 10px 14px;
  border: 1px solid var(--accent);
  border-radius: 8px;
  background: var(--accent-dim);
  color: var(--accent);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.new-chat-btn:hover {
  background: rgba(45, 212, 191, 0.22);
}

.conv-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  min-height: 0; /* 会话多时列表内部滚动，而不是把侧栏撑高 */
  overflow-y: auto;
  /* 窄侧栏里滚动条太占位：隐藏外观，滚轮 / 触控板 / 方向键照常可滚 */
  scrollbar-width: none;
}
.conv-list::-webkit-scrollbar {
  display: none;
}

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 10px 8px 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.conv-item:hover {
  background: var(--bg-elevated);
}
.conv-item.active {
  background: var(--accent-dim);
  border-color: var(--accent);
}
.conv-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0; /* 让标题的 ellipsis 在 flex 子项里生效 */
}
.conv-title {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-time {
  font-size: 11px;
  color: var(--text-dim);
  font-family: var(--mono);
}

/* 删除按钮：默认隐藏，悬停或选中当前会话时出现，键盘聚焦也能看到 */
.conv-delete {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-dim);
  font-size: 15px;
  line-height: 1;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, background 0.15s;
}
.conv-item:hover .conv-delete,
.conv-item.active .conv-delete,
.conv-delete:focus-visible {
  opacity: 1;
}
.conv-delete:hover {
  border-color: rgba(248, 113, 113, 0.45);
  background: rgba(248, 113, 113, 0.12);
  color: var(--danger);
}

.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0; /* grid 子项默认可被内容撑高，置 0 后高度才受行高约束 */
}

.chat-header {
  flex-shrink: 0;
  padding: 20px 28px 12px;
  border-bottom: 1px solid var(--border);
}
.eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
}
.chat-title {
  margin: 4px 0 0;
  font-size: 20px;
  color: var(--text);
}
.chat-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-dim);
}

.messages {
  flex: 1;
  min-height: 0; /* 与 .chat-main 的 min-height:0 配合，消息区才能内部滚动 */
  overflow-y: auto;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty {
  margin: auto;
  color: var(--text-dim);
  font-size: 14px;
}

.message {
  display: flex;
}
.message.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid var(--border);
  background: var(--bg-panel);
}
.message.user .bubble {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: var(--text);
}

/* 助手气泡同时带 markdown 类：marked 渲染的内容由 v-html 插入，
   scoped 样式需用 :deep 穿透；pre-wrap 在此重置为 normal（合并类选择器
   提高优先级，避免依赖声明顺序） */
.bubble.markdown {
  white-space: normal;
}
.markdown :deep(p) {
  margin: 0 0 8px;
}
.markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.markdown :deep(ul),
.markdown :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}
.markdown :deep(li) {
  margin: 2px 0;
}
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  margin: 12px 0 6px;
  font-size: 15px;
}
.markdown :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--accent);
  font-family: var(--mono);
  font-size: 12.5px;
}
.markdown :deep(pre) {
  margin: 8px 0;
  padding: 12px;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #0d1117;
}
.markdown :deep(pre code) {
  padding: 0;
  background: none;
  color: var(--text);
}
.markdown :deep(table) {
  width: 100%;
  margin: 8px 0;
  border-collapse: collapse;
  font-size: 13px;
}
.markdown :deep(th),
.markdown :deep(td) {
  padding: 6px 10px;
  text-align: left;
  border: 1px solid var(--border);
}
.markdown :deep(blockquote) {
  margin: 8px 0;
  padding: 2px 12px;
  border-left: 3px solid var(--accent);
  background: var(--accent-dim);
  color: var(--text-dim);
}
.markdown :deep(a) {
  color: var(--accent);
}
.markdown :deep(hr) {
  margin: 12px 0;
  border: none;
  border-top: 1px solid var(--border);
}

/* 对话不检索知识库：口径边界摆在输入框上方，避免与研究结论混淆 */
.kb-notice {
  display: flex;
  flex-shrink: 0;
  align-items: flex-start;
  gap: 10px;
  margin: 0 28px 4px;
  padding: 10px 14px;
  border: 1px solid rgba(251, 191, 36, 0.28);
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.08);
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.7;
}
.kb-notice strong {
  color: var(--text);
  font-weight: 600;
}
.kb-notice a {
  color: var(--accent);
}
.notice-mark {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  border-radius: 50%;
  background: rgba(251, 191, 36, 0.18);
  color: var(--warn);
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
}

.input-bar {
  display: flex;
  flex-shrink: 0;
  gap: 10px;
  padding: 16px 28px 20px;
  border-top: 1px solid var(--border);
}
.chat-input {
  flex: 1;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-panel);
  color: var(--text);
  font-size: 14px;
  font-family: var(--mono);
  outline: none;
}
.chat-input:focus {
  border-color: var(--accent);
}
.send-btn {
  padding: 0 22px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: #06201c;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
