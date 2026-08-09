// 后端 API 封装：所有请求集中在这里
const BASE_URL = "http://127.0.0.1:8000/api/v1"

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      body.detail ||
        body.error?.message ||
        `请求失败 (${response.status})`
    )
  }

  return response
}

// ===== 知识库 =====

export async function listKnowledgeBases() {
  const response = await request("/knowledge-bases")
  return response.json()
}

export async function createKnowledgeBase(name, description) {
  const response = await request("/knowledge-bases", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  })
  return response.json()
}

export async function listDocuments(knowledgeBaseId) {
  const response = await request(
    `/knowledge-bases/${knowledgeBaseId}/documents`
  )
  return response.json()
}

export async function uploadDocument(knowledgeBaseId, file) {
  const formData = new FormData()
  formData.append("file", file)

  const response = await fetch(
    `${BASE_URL}/knowledge-bases/${knowledgeBaseId}/documents`,
    { method: "POST", body: formData }
  )

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.error?.message || "上传失败")
  }

  return response.json()
}

export async function deleteDocument(knowledgeBaseId, documentId) {
  await request(
    `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}`,
    { method: "DELETE" }
  )
}

// ===== 研究任务 =====

export async function listResearchTasks() {
  const response = await request("/research/tasks")
  return response.json()
}

// 创建研究：SSE 流式返回进度事件
export async function streamResearch(params, onEvent) {
  const response = await fetch(`${BASE_URL}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })

  if (!response.ok) {
    throw new Error(`创建研究失败 (${response.status})`)
  }

  await consumeSse(response, onEvent)
}

// 批准计划：SSE 流式返回执行进度
export async function streamApprove(taskId, approved, onEvent) {
  const response = await fetch(
    `${BASE_URL}/research/tasks/${taskId}/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    }
  )

  if (!response.ok) {
    throw new Error(`操作失败 (${response.status})`)
  }

  await consumeSse(response, onEvent)
}

// 解析 SSE 事件流
async function consumeSse(response, onEvent) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 消息以空行分隔
    const messages = buffer.split("\n\n")
    buffer = messages.pop()

    for (const message of messages) {
      for (const line of message.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)))
          } catch {
            // 忽略无法解析的事件
          }
        }
      }
    }
  }
}
