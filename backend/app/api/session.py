"""会话管理 API (CRUD) - Phase 3 p3-session-api"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.session_service import SessionService
from app.schemas.session import (
    SessionCreate, SessionUpdate, SessionOut, MessageOut,
)

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"module": "session", "status": "ok"}


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """列出所有会话"""
    sessions = await SessionService.list_sessions(db)
    return [SessionOut(**s.to_dict()) for s in sessions]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    """创建新会话"""
    sess = await SessionService.create_session(db, payload.title)
    return SessionOut(**sess.to_dict())


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    sess = await SessionService.get_session(db, session_id)
    if not sess:
        raise HTTPException(404, f"session {session_id} 不存在")
    return SessionOut(**sess.to_dict())


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def rename_session(
    session_id: str,
    payload: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    sess = await SessionService.rename_session(db, session_id, payload.title)
    if not sess:
        raise HTTPException(404, f"session {session_id} 不存在")
    return SessionOut(**sess.to_dict())


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    ok = await SessionService.delete_session(db, session_id)
    if not ok:
        raise HTTPException(404, f"session {session_id} 不存在")
    return None


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def list_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取会话历史消息"""
    sess = await SessionService.get_session(db, session_id)
    if not sess:
        raise HTTPException(404, f"session {session_id} 不存在")
    msgs = await SessionService.list_messages(db, session_id)
    return [MessageOut(**m.to_dict()) for m in msgs]
