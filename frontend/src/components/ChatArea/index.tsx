/**
 * 中间栏 - 问答区域
 * - 输入消息 → chatApi.stream (SSE) → 实时展示 step 进度 + final
 * - Message 来自后端 MessageOut（snake_case + meta.sql/chart/tool_calls/usage）
 */
import { Input, Button, Space, Avatar, Empty, Spin, Tag, Tooltip, Steps, theme } from 'antd'
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  CodeOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useState, useRef, useEffect } from 'react'
import { useChatStore, type Message } from '@/store/chatStore'
import { chatApi } from '@/services/api'

const { TextArea } = Input

// 快捷问题示例（与后端 seed_db 数据集对齐）
const QUICK_QUESTIONS = [
  '查询所有用户的姓名和城市',
  '统计每个城市的用户人数',
  '查询销售额最高的前 3 个产品名',
  '查询 2024-12 到 2025-02 的月销售趋势',
]

// ===== SSE 进度跟踪 =====
interface StreamProgress {
  currentStep: 'pending' | 'list_tables' | 'schema' | 'query_checker' | 'query' | 'finalizing' | 'done'
  toolCalls: Array<{ name: string; status: 'pending' | 'success' | 'error'; preview?: string }>
  sql: string | null
  chartReady: boolean
}

const ChatArea = () => {
  const {
    messages,
    loading,
    currentSessionId,
    appendMessage,
    setLoading,
    setCurrentChart,
  } = useChatStore()

  const [input, setInput] = useState('')
  const [progress, setProgress] = useState<StreamProgress>({
    currentStep: 'pending',
    toolCalls: [],
    sql: null,
    chartReady: false,
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, progress])

  // 自动兜底：若没有 currentSessionId，立即建一个，避免输入框 disabled
  useEffect(() => {
    if (!currentSessionId) {
      void (async () => {
        try {
          const { sessionApi } = await import('@/services/api')
          const sess = await sessionApi.create()
          useChatStore.getState().addSession(sess)
          useChatStore.getState().setCurrentSession(sess.id)
          useChatStore.getState().setMessages([])
        } catch (e) {
          // 拦截器已提示
        }
      })()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId])

  const resetProgress = () =>
    setProgress({ currentStep: 'pending', toolCalls: [], sql: null, chartReady: false })

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userInput = input.trim()

    // 兜底：万一还没 currentSessionId，等它就绪（最多 2s）
    let activeSessionId = currentSessionId
    if (!activeSessionId) {
      for (let i = 0; i < 20 && !activeSessionId; i++) {
        await new Promise((r) => setTimeout(r, 100))
        activeSessionId = useChatStore.getState().currentSessionId
      }
      if (!activeSessionId) {
        // 实在不行，提示用户
        return
      }
    }

    // 乐观追加 user 消息
    const tempUserMsg: Message = {
      id: 0,
      session_id: activeSessionId!,
      role: 'user',
      content: userInput,
      meta: {},
      created_at: new Date().toISOString(),
    }
    appendMessage(tempUserMsg)
    setInput('')
    setLoading(true)
    resetProgress()

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const final = await chatApi.stream(
        { session_id: activeSessionId!, question: userInput },
        (event, data) => {
          switch (event) {
            case 'start':
              setProgress((p) => ({ ...p, currentStep: 'pending' }))
              break
            case 'user_saved':
              // 把临时 user 消息替换为后端真实 id
              useChatStore.setState((s) => ({
                messages: s.messages.map((m) =>
                  m.id === 0 && m.role === 'user' ? { ...m, id: data.user_message_id as number } : m
                ),
              }))
              break
            case 'tool_call': {
              const name = data.name as string
              setProgress((p) => ({
                ...p,
                currentStep: name as StreamProgress['currentStep'],
                toolCalls: [
                  ...p.toolCalls,
                  { name, status: 'pending' },
                ],
              }))
              break
            }
            case 'sql':
              setProgress((p) => ({ ...p, sql: data.sql as string }))
              break
            case 'tool_result': {
              const name = data.name as string
              setProgress((p) => ({
                ...p,
                toolCalls: p.toolCalls.map((tc) =>
                  tc.name === name && tc.status === 'pending'
                    ? {
                        ...tc,
                        status: data.status === 'success' ? 'success' : 'error',
                        preview: data.content_preview as string,
                      }
                    : tc
                ),
              }))
              break
            }
            case 'chart':
              setProgress((p) => ({ ...p, chartReady: true }))
              break
            case 'final':
              // final 时把 user 消息的真实 id 修正，追加 assistant
              {
                const assistant = data.assistant_message as Message
                const user = data.user_message as Message
                useChatStore.setState((s) => ({
                  messages: s.messages.map((m) => (m.id === 0 ? user : m)),
                }))
                appendMessage(assistant)
                if (assistant.meta?.chart) {
                  setCurrentChart(assistant.meta.chart)
                }
              }
              setProgress((p) => ({ ...p, currentStep: 'done' }))
              break
            case 'error':
              setProgress((p) => ({ ...p, currentStep: 'done' }))
              // 移除临时 user
              useChatStore.setState((s) => ({
                messages: s.messages.filter((m) => m.id !== 0),
              }))
              break
          }
        },
        controller.signal
      )
    } catch (e) {
      useChatStore.setState((s) => ({
        messages: s.messages.filter((m) => m.id !== 0),
      }))
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }

  const handleQuickQuestion = (question: string) => {
    setInput(question)
    setTimeout(() => handleSend(), 100)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 0 16px 0' }}>
        {messages.length === 0 ? (
          <Empty
            description={currentSessionId ? '开始对话吧' : '请先新建或选择一个会话'}
            style={{ marginTop: 80 }}
          />
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}

        {loading && <ProgressPanel progress={progress} />}

        {messages.length === 0 && !loading && currentSessionId && (
          <div style={{ marginTop: 24, padding: '0 4px' }}>
            <div style={{ color: '#999', fontSize: 12, marginBottom: 8 }}>试试这些问题：</div>
            <Space wrap>
              {QUICK_QUESTIONS.map((q) => (
                <Tag
                  key={q}
                  icon={<ThunderboltOutlined />}
                  color="processing"
                  style={{ cursor: 'pointer', padding: '4px 8px' }}
                  onClick={() => handleQuickQuestion(q)}
                >
                  {q}
                </Tag>
              ))}
            </Space>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div style={{ borderTop: '1px solid #e8e8e8', padding: 12, backgroundColor: '#fff' }}>
        <div style={{ position: 'relative' }}>
          <TextArea
            placeholder="请输入你的问题...  (Shift+Enter 换行)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            autoSize={{ minRows: 2, maxRows: 6 }}
            style={{ paddingRight: 80 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={() => void handleSend()}
            loading={loading}
            disabled={!input.trim() || loading}
            style={{ position: 'absolute', right: 8, bottom: 8 }}
          >
            发送
          </Button>
        </div>
      </div>
    </div>
  )
}

// 消息气泡
const MessageBubble = ({ message }: { message: Message }) => {
  const isUser = message.role === 'user'
  const meta = message.meta || {}
  const hasSql = !!meta.sql
  const hasToolCalls = !!(meta.tool_calls && meta.tool_calls.length > 0)
  const hasChart = !!meta.chart

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: isUser ? 'row-reverse' : 'row',
        marginBottom: 16,
        paddingLeft: 4,
        paddingRight: 4,
      }}
    >
      <Avatar
        size={32}
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        style={{
          backgroundColor: isUser ? '#87d068' : '#1677ff',
          flexShrink: 0,
          marginLeft: isUser ? 8 : 0,
          marginRight: isUser ? 0 : 8,
        }}
      />
      <div style={{ maxWidth: '75%' }}>
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 8,
            backgroundColor: isUser ? '#1677ff' : '#f5f5f5',
            color: isUser ? '#fff' : 'rgba(0,0,0,0.88)',
            fontSize: 14,
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            boxShadow: isUser
              ? '0 2px 4px rgba(22,119,255,0.15)'
              : '0 1px 2px rgba(0,0,0,0.05)',
          }}
        >
          {message.content}
        </div>

        {/* 标签行：SQL / ToolCalls / Chart 提示 */}
        {!isUser && (hasSql || hasToolCalls || hasChart) && (
          <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {hasChart && (
              <Tag color="cyan" icon={<CodeOutlined />}>
                图表已生成
              </Tag>
            )}
            {hasToolCalls && (
              <Tooltip title={`${meta.tool_calls!.length} 个工具调用`}>
                <Tag color="purple" icon={<ToolOutlined />}>
                  {meta.tool_calls!.length} 工具调用
                </Tag>
              </Tooltip>
            )}
            {meta.usage && (
              <Tag color="default">
                {meta.usage.total_tokens} tokens
              </Tag>
            )}
          </div>
        )}

        {hasSql && <SqlBlock sql={meta.sql!} />}
      </div>
    </div>
  )
}

const SqlBlock = ({ sql }: { sql: string }) => (
  <div
    style={{
      marginTop: 6,
      padding: '8px 10px',
      backgroundColor: '#fafafa',
      border: '1px solid #e8e8e8',
      borderRadius: 4,
      fontSize: 12,
      fontFamily: 'monospace',
      color: '#666',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    }}
  >
    <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>Generated SQL:</div>
    {sql}
  </div>
)

// 进度面板：显示 NL2SQL 的 4 步工具调用 + chart 生成
const STEP_ORDER: Array<{ key: StreamProgress['currentStep']; label: string }> = [
  { key: 'list_tables', label: '查询表' },
  { key: 'schema', label: '取 schema' },
  { key: 'query_checker', label: '自检 SQL' },
  { key: 'query', label: '执行查询' },
  { key: 'finalizing', label: '生成图表' },
]

const ProgressPanel = ({ progress }: { progress: StreamProgress }) => {
  const currentIdx = STEP_ORDER.findIndex((s) => s.key === progress.currentStep)
  return (
    <div
      style={{
        marginTop: 12,
        padding: 12,
        backgroundColor: '#f5f5f5',
        border: '1px solid #e8e8e8',
        borderRadius: 6,
        paddingLeft: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
        <Avatar
          size="small"
          icon={<RobotOutlined />}
          style={{ backgroundColor: '#1677ff', marginRight: 8 }}
        />
        <span style={{ fontSize: 13, color: '#666' }}>AI 正在分析你的问题...</span>
        {progress.currentStep !== 'done' && <Spin size="small" style={{ marginLeft: 'auto' }} />}
      </div>

      <Steps
        size="small"
        current={currentIdx === -1 ? 0 : currentIdx}
        style={{ marginBottom: 8 }}
        items={STEP_ORDER.map((s) => ({
          title: s.label,
        }))}
      />

      {progress.sql && (
        <div
          style={{
            marginTop: 6,
            padding: '6px 8px',
            backgroundColor: '#fff',
            border: '1px dashed #91caff',
            borderRadius: 4,
            fontSize: 11,
            fontFamily: 'monospace',
            color: '#1677ff',
          }}
        >
          <div style={{ fontSize: 10, color: '#999', marginBottom: 2 }}>SQL (已生成)</div>
          {progress.sql}
        </div>
      )}

      {progress.toolCalls.length > 0 && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#999' }}>
          {progress.toolCalls.map((tc, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', marginTop: 2 }}>
              {tc.status === 'success' ? (
                <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
              ) : tc.status === 'error' ? (
                <span style={{ color: '#f5222d', marginRight: 4 }}>✗</span>
              ) : (
                <LoadingOutlined style={{ color: '#1677ff', marginRight: 4 }} />
              )}
              <span>
                {tc.name}
                {tc.preview ? `: ${tc.preview.slice(0, 60)}${tc.preview.length > 60 ? '...' : ''}` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// 显式导出一个清理函数以便外部测试触发
export const __clearMessages = () => useChatStore.getState().clearMessages()

export default ChatArea
