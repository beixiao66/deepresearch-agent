// 后端 API 封装：所有请求集中在这里
import { showErrorDialog } from "./errorDialog"

const BASE_URL = "http://127.0.0.1:8000/api/v1"

function getErrorMessage(body, fallback) {
  if (typeof body?.error?.message === "string") {
    return body.error.message
  }
  if (typeof body?.detail === "string") {
    return body.detail
  }
  return fallback
}

async function throwRequestError(response, fallback) {
  const body = await response.json().catch(() => ({}))
  const error = new Error(getErrorMessage(body, fallback))
  showErrorDialog(error)
  throw error
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    })
  } catch (error) {
    const connectionError = new Error("无法连接服务器，请检查服务是否已启动")
    showErrorDialog(connectionError)
    throw connectionError
  }

  if (!response.ok) {
    await throwRequestError(response, `请求失败 (${response.status})`)
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

export async function deleteKnowledgeBase(knowledgeBaseId) {
  await request(`/knowledge-bases/${knowledgeBaseId}`, {
    method: "DELETE",
  })
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

  let response
  try {
    response = await fetch(
      `${BASE_URL}/knowledge-bases/${knowledgeBaseId}/documents`,
      { method: "POST", body: formData }
    )
  } catch {
    const error = new Error("无法连接服务器，请检查服务是否已启动")
    showErrorDialog(error)
    throw error
  }

  if (!response.ok) {
    await throwRequestError(response, "上传失败")
  }

  return response.json()
}

export async function retryDocument(knowledgeBaseId, documentId) {
  const response = await request(
    `/knowledge-bases/${knowledgeBaseId}/documents/${documentId}/retry`,
    { method: "POST" }
  )
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
  let response
  try {
    response = await fetch(`${BASE_URL}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    })
  } catch {
    const error = new Error("无法连接服务器，请检查服务是否已启动")
    showErrorDialog(error)
    throw error
  }

  if (!response.ok) {
    await throwRequestError(response, `创建研究失败 (${response.status})`)
  }

  try {
    await consumeSse(response, onEvent)
  } catch (error) {
    showErrorDialog(error)
    throw error
  }
}

// 批准计划：SSE 流式返回执行进度
export async function streamApprove(taskId, approved, onEvent) {
  let response
  try {
    response = await fetch(
      `${BASE_URL}/research/tasks/${taskId}/approve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved }),
      }
    )
  } catch {
    const error = new Error("无法连接服务器，请检查服务是否已启动")
    showErrorDialog(error)
    throw error
  }

  if (!response.ok) {
    await throwRequestError(response, `操作失败 (${response.status})`)
  }

  try {
    await consumeSse(response, onEvent)
  } catch (error) {
    showErrorDialog(error)
    throw error
  }
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
          let event
          try {
            event = JSON.parse(line.slice(6))
          } catch {
            throw new Error("服务器返回了无法解析的数据")
          }
          if (event.type === "error") {
            throw new Error(
              event.message || "研究任务执行失败，请稍后重试"
            )
          }
          onEvent(event)
        }
      }
    }
  }
}
