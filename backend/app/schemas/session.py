"""会话 / 消息 / 聊天 相关 Pydantic 模型"""
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


# === Session ===
class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# === Message ===
class ChartData(BaseModel):
    """前端 Chart.js 所需结构"""
    type: Literal["line", "bar", "pie", "table"] = "bar"
    title: Optional[str] = None
    labels: list[str] = []
    datasets: list[dict] = []
    tableData: Optional[list[dict]] = None


class MessageOut(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant", "tool", "system"]
    content: str
    meta: dict = Field(default_factory=dict)
    created_at: Optional[str] = None


# === Chat ===
class ChatRequest(BaseModel):
    """聊天请求（非流式）"""
    session_id: str
    question: str = Field(..., min_length=1, max_length=2000)
    stream: bool = False  # True 走 SSE


class ChartInMeta(BaseModel):
    """assistant 消息 meta 中的图表数据（可选）"""
    sql: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    chart: Optional[ChartData] = None
    finish_reason: Optional[str] = None
    usage: Optional[dict] = None


class ChatResponse(BaseModel):
    """聊天响应（非流式）"""
    session_id: str
    user_message: MessageOut
    assistant_message: MessageOut
