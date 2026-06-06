"""数据库 Schema 元数据缓存表（用于 NL2SQL 的 schema 列表缓存）"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SchemaMeta(Base):
    """业务表元数据缓存"""
    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. "tables" | "schema:<table>"
    value: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
