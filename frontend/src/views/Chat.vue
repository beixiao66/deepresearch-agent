<script setup>
import { nextTick, onMounted, ref } from "vue"
import {
  chatMessage,
  getConversationMessages,
  listConversations,
} from "../api"

const conversations = ref([])
const currentId = ref(localStorage.getItem("chat_conversation_id") || null)
const messages = ref([])
const draft = ref("")
const sending = ref(false)
const messagesRef = ref(null)

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
          <span class="conv-title">{{ conversation.title }}</span>
          <span class="conv-time">
            {{ new Date(conversation.updated_at).toLocaleDateString() }}
          </span>
        </div>
      </div>
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <span class="eyebrow">CHAT WORKSPACE</span>
        <h2 class="chat-title">DeepResearch 对话</h2>
        <p class="chat-subtitle">
          多轮对话记忆 · 基于对话历史给出建议
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
          <div class="bubble">{{ message.content }}</div>
        </div>
      </div>

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
  gap: 0;
  min-height: calc(100vh - 80px);
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.chat-sidebar {
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 12px;
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
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.conv-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.conv-item:hover {
  background: var(--bg-elevated);
}
.conv-item.active {
  background: var(--accent-dim);
  border-color: var(--accent);
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

.chat-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
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

.input-bar {
  display: flex;
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
