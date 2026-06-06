"""
聊天业务编排
- 加载会话历史（memory）
- 调用 NL2SQL 服务
- 持久化消息
"""
import json
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.session_service import SessionService
from app.services.nl2sql_service import run_nl2sql_sync
from app.services.memory_service import get_session_history
from app.schemas.session import MessageOut


class ChatService:
    @staticmethod
    async def chat(
        db: AsyncSession,
        session_id: str,
        question: str,
    ) -> dict:
        """非流式聊天入口"""
        # 1. 确认 session 存在
        sess = await SessionService.get_session(db, session_id)
        if not sess:
            raise ValueError(f"session {session_id} 不存在")

        # 2. 加载历史 → 喂给 agent
        history = await get_session_history(db, session_id).aget_messages()
        # 去掉最后一条 welcome
        # 让 agent 看到"对话上下文"（除欢迎消息外）
        ctx_messages = history[:-1] if len(history) > 1 else []

        # 3. 持久化用户消息
        user_msg = await SessionService.append_message(
            db, session_id, "user", question
        )

        # 4. 调用 NL2SQL
        result = run_nl2sql_sync(db, question, history_messages=ctx_messages)

        # 5. 持久化 assistant 消息
        meta = {
            "sql": result.get("sql"),
            "tool_calls": result.get("tool_calls"),
            "chart": result.get("chart"),
            "usage": result.get("usage"),
        }
        ai_msg = await SessionService.append_message(
            db, session_id, "assistant", result["answer"], meta=meta
        )

        # 6. 自动用首条用户问题更新 session title
        if sess.title == "新会话" and question:
            new_title = question[:30] + ("..." if len(question) > 30 else "")
            await SessionService.rename_session(db, session_id, new_title)
            sess.title = new_title

        return {
            "session_id": session_id,
            "user_message": MessageOut(**user_msg.to_dict()).model_dump(),
            "assistant_message": MessageOut(**ai_msg.to_dict()).model_dump(),
        }
