"""会话 / 消息 业务逻辑"""
import json
from typing import AsyncIterator
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, Message


class SessionService:
    @staticmethod
    async def list_sessions(db: AsyncSession) -> list[Session]:
        result = await db.execute(select(Session).order_by(Session.updated_at.desc()))
        return list(result.scalars())

    @staticmethod
    async def get_session(db: AsyncSession, session_id: str) -> Session | None:
        return await db.get(Session, session_id)

    @staticmethod
    async def create_session(db: AsyncSession, title: str | None = None) -> Session:
        # 若未传标题，新建后用首条消息来更新（这里用默认值即可）
        sess = Session(title=title or "新会话")
        db.add(sess)
        # 先 flush 拿到 id，再建 welcome（避免 session_id 为 None）
        await db.flush()
        welcome = Message(
            session_id=sess.id,
            role="assistant",
            content="你好！我是智能数据分析助理，可以用自然语言帮你查询数据库并生成可视化图表。",
            meta=json.dumps({}, ensure_ascii=False),
        )
        db.add(welcome)
        await db.commit()
        await db.refresh(sess)
        return sess

    @staticmethod
    async def rename_session(db: AsyncSession, session_id: str, title: str) -> Session | None:
        sess = await db.get(Session, session_id)
        if not sess:
            return None
        sess.title = title
        await db.commit()
        await db.refresh(sess)
        return sess

    @staticmethod
    async def delete_session(db: AsyncSession, session_id: str) -> bool:
        # 级联删除 messages 由 ORM cascade 处理
        sess = await db.get(Session, session_id)
        if not sess:
            return False
        await db.delete(sess)
        await db.commit()
        return True

    @staticmethod
    async def list_messages(db: AsyncSession, session_id: str) -> list[Message]:
        result = await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
        )
        return list(result.scalars())

    @staticmethod
    async def append_message(
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        meta: dict | None = None,
    ) -> Message:
        msg = Message(
            session_id=session_id,
            role=role,
            content=content or "",
            meta=json.dumps(meta or {}, ensure_ascii=False),
        )
        db.add(msg)
        # 触碰 session.updated_at
        sess = await db.get(Session, session_id)
        if sess:
            from datetime import datetime
            sess.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(msg)
        return msg
