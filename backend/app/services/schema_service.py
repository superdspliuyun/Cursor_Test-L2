"""
数据库 Schema 服务
- 反射 SQLite 中所有业务表
- 提供 list_tables / get_schema(table_names) 两个核心方法
- 结果缓存到 schema_meta 表，节省 LLM token
"""
import json
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SchemaMeta
from app.db.database import engine
from app.config import get_settings


CACHE_TTL_SECONDS = 300  # 5 分钟


class SchemaService:
    @staticmethod
    async def list_tables(db: AsyncSession, force_refresh: bool = False) -> list[str]:
        """列出所有业务表名（带缓存）"""
        if not force_refresh:
            cached = await SchemaService._get_cache(db, "tables")
            if cached:
                return cached

        tables = await SchemaService._reflect_tables()
        await SchemaService._set_cache(db, "tables", tables)
        return tables

    @staticmethod
    async def get_schema(
        db: AsyncSession, table_names: list[str], force_refresh: bool = False
    ) -> list[dict]:
        """获取指定表的 DDL + 样例行"""
        results = []
        for name in table_names:
            cache_key = f"schema:{name}"
            if not force_refresh:
                cached = await SchemaService._get_cache(db, cache_key)
                if cached:
                    results.append(cached)
                    continue

            info = await SchemaService._reflect_table(name)
            if info:
                results.append(info)
                await SchemaService._set_cache(db, cache_key, info)
        return results

    @staticmethod
    async def _reflect_tables() -> list[str]:
        s = get_settings()
        # 提取 sqlite 文件路径
        # url 形如 sqlite+aiosqlite:///./data/app.db
        path = s.DATABASE_URL.split("///")[-1]
        # 用同步 sqlite3 反射（轻量、稳定）
        import sqlite3
        conn = sqlite3.connect(path)
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            tables = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()
        return tables

    @staticmethod
    async def _reflect_table(name: str) -> dict | None:
        s = get_settings()
        path = s.DATABASE_URL.split("///")[-1]
        import sqlite3
        conn = sqlite3.connect(path)
        try:
            cur = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            )
            row = cur.fetchone()
            if not row:
                return None
            ddl = row[0]
            cur2 = conn.execute(f"SELECT * FROM {name} LIMIT 3")
            cols = [d[0] for d in cur2.description]
            rows = [list(r) for r in cur2.fetchall()]
            return {
                "name": name,
                "ddl": ddl,
                "columns": cols,
                "sample_rows": rows,
            }
        finally:
            conn.close()

    @staticmethod
    async def _get_cache(db: AsyncSession, key: str):
        result = await db.execute(select(SchemaMeta).where(SchemaMeta.key == key))
        row = result.scalar_one_or_none()
        if not row:
            return None
        # TTL 检查
        if row.updated_at:
            age = (datetime.utcnow() - row.updated_at).total_seconds()
            if age > CACHE_TTL_SECONDS:
                return None
        try:
            return json.loads(row.value)
        except Exception:
            return None

    @staticmethod
    async def _set_cache(db: AsyncSession, key: str, value):
        result = await db.execute(select(SchemaMeta).where(SchemaMeta.key == key))
        row = result.scalar_one_or_none()
        text_val = json.dumps(value, ensure_ascii=False)
        if row:
            row.value = text_val
            row.updated_at = datetime.utcnow()
        else:
            db.add(SchemaMeta(key=key, value=text_val))
        await db.commit()
