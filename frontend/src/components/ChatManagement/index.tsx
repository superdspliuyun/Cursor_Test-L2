/**
 * 左侧栏 - 聊天会话管理
 * 全部走 sessionApi（@/services/api）
 */
import { Button, List, Input, Modal, Dropdown, message, Empty, Tooltip, Spin } from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  MessageOutlined,
  EditOutlined,
  MoreOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { useState, useMemo, useEffect } from 'react'
import { useChatStore } from '@/store/chatStore'
import { sessionApi } from '@/services/api'

const { Search } = Input

const formatTime = (iso?: string | null) => {
  if (!iso) return ''
  return iso.replace('T', ' ').slice(0, 16)
}

const ChatManagement = () => {
  const {
    sessions,
    currentSessionId,
    setSessions,
    addSession,
    updateSession,
    removeSession,
    setCurrentSession,
    setMessages,
  } = useChatStore()

  const [searchText, setSearchText] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const [loading, setLoading] = useState(false)

  // 启动时拉取真数据
  useEffect(() => {
    void (async () => {
      setLoading(true)
      try {
        const list = await sessionApi.list()
        setSessions(list)
        // 默认选第一个
        if (list.length > 0) {
          const first = list[0]
          setCurrentSession(first.id)
          const msgs = await sessionApi.listMessages(first.id)
          setMessages(msgs)
        }
      } catch (e) {
        // 错误提示由 axios 拦截器统一处理
      } finally {
        setLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filteredSessions = useMemo(() => {
    if (!searchText) return sessions
    return sessions.filter((s) =>
      s.title.toLowerCase().includes(searchText.toLowerCase())
    )
  }, [sessions, searchText])

  const handleNew = async () => {
    try {
      const sess = await sessionApi.create()
      addSession(sess)
      setCurrentSession(sess.id)
      setMessages([])
      message.success('已创建新会话')
    } catch {
      /* 拦截器已提示 */
    }
  }

  const handleDelete = (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定要删除该会话吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await sessionApi.remove(id)
          removeSession(id)
          // 如果删的是当前会话，重新拉一次历史
          if (id === currentSessionId) {
            const newId = useChatStore.getState().currentSessionId
            if (newId) {
              const msgs = await sessionApi.listMessages(newId)
              setMessages(msgs)
            } else {
              setMessages([])
            }
          }
          message.success('已删除会话')
        } catch {
          /* 拦截器已提示 */
        }
      },
    })
  }

  const handleSwitch = async (id: string) => {
    if (id === currentSessionId) return
    setCurrentSession(id)
    try {
      const msgs = await sessionApi.listMessages(id)
      setMessages(msgs)
    } catch {
      setMessages([])
    }
  }

  const startRename = (id: string, title: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(id)
    setEditingTitle(title)
  }

  const saveRename = async () => {
    if (editingId && editingTitle.trim()) {
      const newTitle = editingTitle.trim()
      try {
        const updated = await sessionApi.rename(editingId, newTitle)
        updateSession(editingId, { title: updated.title })
        message.success('已重命名')
      } catch {
        /* 拦截器已提示 */
      }
    }
    setEditingId(null)
    setEditingTitle('')
  }

  return (
    <div>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={handleNew}
        block
        style={{ marginBottom: 12 }}
      >
        新建会话
      </Button>

      <Search
        placeholder="搜索会话"
        allowClear
        size="small"
        prefix={<SearchOutlined />}
        value={searchText}
        onChange={(e) => setSearchText(e.target.value)}
        style={{ marginBottom: 12 }}
      />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin size="small" />
        </div>
      ) : filteredSessions.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={searchText ? '无匹配会话' : '暂无会话，点击上方"新建会话"开始'}
          style={{ marginTop: 40 }}
        />
      ) : (
        <List
          dataSource={filteredSessions}
          renderItem={(item) => {
            const isActive = currentSessionId === item.id
            const isEditing = editingId === item.id

            return (
              <List.Item
                style={{
                  cursor: 'pointer',
                  padding: '10px 12px',
                  backgroundColor: isActive ? '#e6f4ff' : 'transparent',
                  borderRadius: 6,
                  marginBottom: 4,
                  border: isActive ? '1px solid #91caff' : '1px solid transparent',
                  transition: 'all 0.2s',
                }}
                onClick={() => !isEditing && handleSwitch(item.id)}
                actions={
                  isEditing
                    ? []
                    : [
                        <Dropdown
                          key="more"
                          menu={{
                            items: [
                              {
                                key: 'rename',
                                label: '重命名',
                                icon: <EditOutlined />,
                                onClick: ({ domEvent }) =>
                                  startRename(item.id, item.title, domEvent as React.MouseEvent),
                              },
                              { type: 'divider' },
                              {
                                key: 'delete',
                                label: '删除',
                                icon: <DeleteOutlined />,
                                danger: true,
                                onClick: ({ domEvent }) =>
                                  handleDelete(item.id, domEvent as React.MouseEvent),
                              },
                            ],
                          }}
                          trigger={['click']}
                          placement="bottomRight"
                        >
                          <MoreOutlined
                            onClick={(e) => e.stopPropagation()}
                            style={{ padding: 4 }}
                          />
                        </Dropdown>,
                      ]
                }
              >
                <List.Item.Meta
                  avatar={<MessageOutlined style={{ color: isActive ? '#1677ff' : '#999' }} />}
                  title={
                    isEditing ? (
                      <Input
                        size="small"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onPressEnter={saveRename}
                        onBlur={saveRename}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <Tooltip title={item.title} placement="topLeft">
                        <span
                          style={{
                            fontSize: 13,
                            fontWeight: isActive ? 500 : 400,
                            color: isActive ? '#1677ff' : 'inherit',
                            display: 'block',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {item.title}
                        </span>
                      </Tooltip>
                    )
                  }
                  description={
                    <span style={{ fontSize: 11, color: '#999' }}>
                      {formatTime(item.updated_at)}
                    </span>
                  }
                />
              </List.Item>
            )
          }}
        />
      )}
    </div>
  )
}

export default ChatManagement
