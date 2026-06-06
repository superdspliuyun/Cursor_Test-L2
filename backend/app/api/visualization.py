"""可视化 / 数据库 Schema API - Phase 3 p3-schema-api"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.schema_service import SchemaService
from app.services.chart_service import build_chart
from app.schemas.schema_meta import SchemaOut, TableInfo

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"module": "visualization", "status": "ok"}


@router.get("/database/schema", response_model=SchemaOut)
async def get_schema(
    refresh: bool = Query(False, description="强制刷新缓存"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取数据库中所有业务表的 schema
    默认带 5 分钟缓存；refresh=true 强制重建
    """
    tables = await SchemaService.list_tables(db, force_refresh=refresh)
    schema_infos = await SchemaService.get_schema(db, tables, force_refresh=refresh)

    items = []
    for info in schema_infos:
        items.append(TableInfo(
            name=info["name"],
            ddl=info["ddl"],
            sample_rows=info["sample_rows"],
        ))

    from datetime import datetime
    return SchemaOut(tables=items, refreshed_at=datetime.utcnow().isoformat())


@router.get("/database/tables")
async def list_tables(
    refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """轻量级：仅返回表名列表"""
    tables = await SchemaService.list_tables(db, force_refresh=refresh)
    return {"tables": tables, "count": len(tables)}
