"""Schema 元数据 API 协议"""
from pydantic import BaseModel
from typing import Optional


class TableInfo(BaseModel):
    name: str
    ddl: str
    sample_rows: list[list] = []


class SchemaOut(BaseModel):
    tables: list[TableInfo]
    refreshed_at: Optional[str] = None
