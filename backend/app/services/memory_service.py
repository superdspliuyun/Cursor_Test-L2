"""
上下文记忆服务
基于 LangChain v1 的 ChatMessageHistory + 会话级存储
"""
from typing import List
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.services.session_service import SessionService
from sqlalchemy.ext.asyncio import AsyncSession


class SQLiteChatMessageHistory(BaseChatMessageHistory):
    """将会话消息历史持久化到 SQLite（无 LangChain 内置实现，自己写）"""

    def __init__(self, db: AsyncSession, session_id: str):
        self._db = db
        self._session_id = session_id

    @property
    def messages(self) -> List[BaseMessage]:
        """同步访问；推荐用 aget_messages"""
        raise NotImplementedError("Use aget_messages instead")

    async def aget_messages(self) -> List[BaseMessage]:
        msgs = await SessionService.list_messages(self._db, self._session_id)
        result: List[BaseMessage] = []
        for m in msgs:
            if m.role == "user":
                result.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                result.append(AIMessage(content=m.content))
            # tool / system 暂不进入 memory（避免污染主上下文）
        return result

    async def aadd_messages(self, messages: List[BaseMessage]) -> None:
        for m in messages:
            role = "user" if isinstance(m, HumanMessage) else "assistant"
            await SessionService.append_message(
                self._db, self._session_id, role, m.content
            )

    async def aclear(self) -> None:
        from app.models import Message
        from sqlalchemy import delete
        await self._db.execute(
            delete(Message).where(Message.session_id == self._session_id)
        )
        await self._db.commit()

    def clear(self) -> None:
        """同步占位（LangChain 1.x BaseChatMessageHistory 抽象方法）"""
        raise NotImplementedError("Use aclear instead")

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """同步占位（LangChain 1.x BaseChatMessageHistory 抽象方法）"""
        raise NotImplementedError("Use aadd_messages instead")


def get_session_history(db: AsyncSession, session_id: str) -> SQLiteChatMessageHistory:
    """工厂：获取会话级 history"""
    return SQLiteChatMessageHistory(db, session_id)
