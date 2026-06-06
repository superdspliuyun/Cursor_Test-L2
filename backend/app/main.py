"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db
from app.api import chat, session, visualization

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化数据库（确保所有 ORM 模型已 import）
    from app.models import Session, Message, SchemaMeta  # noqa: F401
    await init_db()

    # 预热 schema 缓存（可选）
    from app.db.database import AsyncSessionLocal
    from app.services.schema_service import SchemaService
    async with AsyncSessionLocal() as db:
        try:
            await SchemaService.list_tables(db, force_refresh=False)
        except Exception as e:
            print(f"[startup] schema warmup failed: {e}")

    yield
    # 关闭时清理资源


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 Qwen3 的自然语言数据分析系统",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(session.router, prefix="/api/session", tags=["session"])
app.include_router(visualization.router, prefix="/api/visualization", tags=["visualization"])


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
    }
