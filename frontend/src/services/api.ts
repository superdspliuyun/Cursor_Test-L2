/**
 * API 服务层
 * 与后端 FastAPI 路由对齐
 *   后端路由前缀：/api/{session, chat, visualization}
 *   字段命名：snake_case（与 Pydantic 一致）
 */
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { message as antdMessage } from 'antd'

// ===== 类型定义（与后端 Pydantic 对齐） =====

export interface SessionOut {
  id: string
  title: string
  created_at: string | null
  updated_at: string | null
}

export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'table'
  title?: string | null
  labels: string[]
  datasets: Array<{
    label: string
    data: number[]
    backgroundColor?: string | string[]
    borderColor?: string
    tension?: number
    fill?: boolean
  }>
  tableData?: Array<Record<string, unknown>> | null
}

export interface MessageMeta {
  sql?: string | null
  chart?: ChartData | null
  tool_calls?: Array<{ name: string; id: string; args: Record<string, unknown> }>
  usage?: { input_tokens: number; output_tokens: number; total_tokens: number }
  finish_reason?: string
}

export interface MessageOut {
  id: number
  session_id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  meta: MessageMeta
  created_at: string | null
}

export interface ChatResponse {
  session_id: string
  user_message: MessageOut
  assistant_message: MessageOut
}

export interface TableInfo {
  name: string
  ddl: string
  sample_rows: unknown[][]
}

export interface SchemaOut {
  tables: TableInfo[]
  refreshed_at: string | null
}

// ===== axios 实例 =====

const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => config)

apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ detail?: string }>) => {
    const detail =
      error.response?.data?.detail ||
      error.message ||
      '请求失败'
    if (error.response) {
      const code = error.response.status
      if (code >= 500) {
        antdMessage.error(`[${code}] ${detail}`)
      } else if (code === 404) {
        antdMessage.error(`未找到资源：${detail}`)
      } else {
        antdMessage.error(detail)
      }
    } else {
      antdMessage.error(`网络错误：${detail}`)
    }
    return Promise.reject(error)
  }
)

// ===== API 命名空间 =====

export const healthCheck = () => apiClient.get('/../health') as unknown as Promise<{ status: string; app: string; version: string }>

export const sessionApi = {
  /** 列出所有会话（按 updated_at desc） */
  list: () => apiClient.get<SessionOut[]>('/session/sessions') as unknown as Promise<SessionOut[]>,

  /** 创建会话 */
  create: (title?: string) =>
    apiClient.post<SessionOut>('/session/sessions', { title }) as unknown as Promise<SessionOut>,

  /** 获取单个会话 */
  get: (id: string) =>
    apiClient.get<SessionOut>(`/session/sessions/${id}`) as unknown as Promise<SessionOut>,

  /** 重命名 */
  rename: (id: string, title: string) =>
    apiClient.patch<SessionOut>(`/session/sessions/${id}`, { title }) as unknown as Promise<SessionOut>,

  /** 删除 */
  remove: (id: string) =>
    apiClient.delete(`/session/sessions/${id}`) as Promise<null>,

  /** 获取会话的所有消息 */
  listMessages: (id: string) =>
    apiClient.get<MessageOut[]>(`/session/sessions/${id}/messages`) as unknown as Promise<MessageOut[]>,
}

export const chatApi = {
  /** 非流式聊天 */
  query: (payload: { session_id: string; question: string; stream?: boolean }) =>
    apiClient.post<ChatResponse>('/chat/chat', payload) as unknown as Promise<ChatResponse>,

  /**
   * SSE 流式聊天
   * @param onEvent 接收每条 SSE 事件的回调
   * @param signal  AbortController.signal 用于取消
   * @returns 最终的 assistant_message
   */
  stream: async (
    payload: { session_id: string; question: string },
    onEvent: (event: string, data: Record<string, unknown>) => void,
    signal?: AbortSignal
  ): Promise<{ assistant_message: MessageOut; user_message: MessageOut } | null> => {
    const url = `/api/chat/chat/stream`
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })
    if (!res.ok || !res.body) {
      throw new Error(`SSE failed: ${res.status}`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let finalPayload: { assistant_message: MessageOut; user_message: MessageOut } | null = null

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 事件以 \n\n 分隔
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''
      for (const ev of events) {
        const line = ev.split('\n').find((l) => l.startsWith('data: '))
        if (!line) continue
        const jsonStr = line.slice(6)
        try {
          const parsed = JSON.parse(jsonStr) as { event: string; data: Record<string, unknown> }
          onEvent(parsed.event, parsed.data)
          if (parsed.event === 'final') {
            finalPayload = parsed.data as unknown as {
              assistant_message: MessageOut
              user_message: MessageOut
            }
          }
        } catch (e) {
          console.warn('[SSE] parse failed', e, jsonStr)
        }
      }
    }
    return finalPayload
  },
}

export const schemaApi = {
  /** 完整 schema（带 DDL 与 sample rows） */
  get: (refresh = false) =>
    apiClient.get<SchemaOut>('/visualization/database/schema', { params: { refresh } }) as unknown as Promise<SchemaOut>,

  /** 仅表名 */
  listTables: (refresh = false) =>
    apiClient.get<{ tables: string[]; count: number }>('/visualization/database/tables', { params: { refresh } }) as unknown as Promise<{ tables: string[]; count: number }>,
}

export default apiClient
