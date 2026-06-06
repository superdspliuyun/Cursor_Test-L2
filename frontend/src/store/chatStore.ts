/**
 * 聊天状态管理 Store
 * 字段命名与后端 Pydantic 模型完全一致（snake_case）
 * id 兼容 string | number（前端可临时用 string 占位，最终以后端为准）
 */
import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { ChartData, MessageOut, SessionOut } from '@/services/api'

export type Session = SessionOut
export type Message = MessageOut

interface ChatState {
  // 会话
  sessions: Session[]
  currentSessionId: string | null

  // 消息
  messages: Message[]
  loading: boolean

  // UI
  currentChart: ChartData | null
  chartType: 'line' | 'bar' | 'pie' | 'table'

  // 会话 actions
  setSessions: (list: Session[]) => void
  addSession: (s: Session) => void
  updateSession: (id: string, partial: Partial<Session>) => void
  removeSession: (id: string) => void
  setCurrentSession: (id: string | null) => void

  // 消息 actions
  setMessages: (msgs: Message[]) => void
  appendMessage: (m: Message) => void
  setLoading: (loading: boolean) => void
  clearMessages: () => void

  // UI actions
  setCurrentChart: (chart: ChartData | null) => void
  setChartType: (type: 'line' | 'bar' | 'pie' | 'table') => void
}

export const useChatStore = create<ChatState>()(
  devtools(
    (set) => ({
      sessions: [],
      currentSessionId: null,
      messages: [],
      loading: false,
      currentChart: null,
      chartType: 'bar',

      setSessions: (list) => set({ sessions: list }),

      addSession: (s) =>
        set((state) => ({ sessions: [s, ...state.sessions] })),

      updateSession: (id, partial) =>
        set((state) => ({
          sessions: state.sessions.map((s) => (s.id === id ? { ...s, ...partial } : s)),
        })),

      removeSession: (id) =>
        set((state) => {
          const newSessions = state.sessions.filter((s) => s.id !== id)
          return {
            sessions: newSessions,
            currentSessionId:
              state.currentSessionId === id ? newSessions[0]?.id ?? null : state.currentSessionId,
            messages: state.currentSessionId === id ? [] : state.messages,
            currentChart: state.currentSessionId === id ? null : state.currentChart,
          }
        }),

      setCurrentSession: (id) => set({ currentSessionId: id, currentChart: null, messages: [] }),

      setMessages: (msgs) => set({ messages: msgs }),

      appendMessage: (m) => set((state) => ({ messages: [...state.messages, m] })),

      setLoading: (loading) => set({ loading }),
      clearMessages: () => set({ messages: [], currentChart: null }),

      setCurrentChart: (chart) => set({ currentChart: chart }),
      setChartType: (type) => set({ chartType: type }),
    }),
    { name: 'chat-store' }
  )
)
