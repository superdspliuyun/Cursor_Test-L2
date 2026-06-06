"""
NL2SQL 服务
基于 LangChain v1 create_agent() + 4 个 SQL @tool
依据 ADR-003（实现路径）+ ADR-004（字段规范）

工作流：
  list_tables → schema → query_checker → query → 总结
"""
import json
from typing import AsyncIterator
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, BaseMessage

from app.config import get_settings
from app.services.llm_service import get_qwen3_chat_model, extract_usage
from app.services.schema_service import SchemaService
from app.services.chart_service import build_chart
from app.services.memory_service import get_session_history
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================
# 1. 4 个 SQL 工具（与 ADR-003 严格同名）
# ============================================================
@tool
def sql_db_list_tables() -> str:
    """List all tables available in the database. Input is an empty string, output is a comma-separated list of tables."""
    return ""  # 占位；实际在 build_agent 时替换为带 db 的闭包版本


@tool
def sql_db_schema(table_names: str) -> str:
    """Get the schema and sample rows for the specified tables. Input is a comma-separated list of table names. Always call sql_db_list_tables first to confirm table names exist!"""
    return ""


@tool
def sql_db_query(query: str) -> str:
    """Execute a SQL query against the database. Input is a detailed and correct SQL query, output is the result. If you encounter an issue with Unknown column, use sql_db_schema first."""
    return ""


@tool
def sql_db_query_checker(query: str) -> str:
    """Use this tool to double-check if your SQL query is correct before executing it. Always use this before sql_db_query!"""
    return ""


# ============================================================
# 2. 工具工厂：注入 db session
# ============================================================
def make_sql_tools(db: AsyncSession) -> list:
    """根据 db session 生成真正的工具（带状态的闭包）"""
    from app.config import get_settings
    import sqlite3

    def _conn():
        s = get_settings()
        path = s.DATABASE_URL.split("///")[-1]
        return sqlite3.connect(path)

    @tool
    def sql_db_list_tables() -> str:
        """List all tables available in the database. Input is empty string, output is a comma-separated list of tables."""
        try:
            conn = _conn()
            try:
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
                return ", ".join(r[0] for r in cur.fetchall())
            finally:
                conn.close()
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    @tool
    def sql_db_schema(table_names: str) -> str:
        """Get the schema and sample rows for the specified tables. Input is a comma-separated list of table names. Always call sql_db_list_tables first!"""
        try:
            conn = _conn()
            try:
                names = [n.strip() for n in table_names.split(",") if n.strip()]
                out = []
                for name in names:
                    cur = conn.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (name,),
                    )
                    row = cur.fetchone()
                    if not row:
                        out.append(f"Table {name} not found")
                        continue
                    ddl = row[0]
                    cur2 = conn.execute(f"SELECT * FROM {name} LIMIT 3")
                    cols = [d[0] for d in cur2.description]
                    rows = cur2.fetchall()
                    out.append(
                        f"Table: {name}\nDDL: {ddl}\nColumns: {cols}\nSample rows:\n"
                        + "\n".join(str(r) for r in rows)
                    )
                return "\n\n".join(out) if out else f"No tables found: {names}"
            finally:
                conn.close()
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    @tool
    def sql_db_query(query: str) -> str:
        """Execute a SQL query against the database. Input is a detailed and correct SQL query, output is the result. If you encounter an issue with Unknown column, use sql_db_schema first."""
        try:
            conn = _conn()
            try:
                cur = conn.execute(query)
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    rows = [list(r) for r in cur.fetchall()]
                    return f"Columns: {cols}\nRows:\n" + "\n".join(str(r) for r in rows)
                else:
                    return f"OK. rows_affected: {cur.rowcount}"
            finally:
                conn.close()
        except Exception as e:
            # 按 ADR-003 铁律：error 返回给 LLM 而非抛异常
            return f"Error: {type(e).__name__}: {e}"

    @tool
    def sql_db_query_checker(query: str) -> str:
        """Use this tool to double-check if your SQL query is correct before executing it. Always use this before sql_db_query!"""
        try:
            conn = _conn()
            try:
                conn.execute(f"EXPLAIN {query}")
                return "OK. Query parsed successfully."
            finally:
                conn.close()
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    return [sql_db_list_tables, sql_db_schema, sql_db_query, sql_db_query_checker]


# ============================================================
# 3. Agent 工厂
# ============================================================
SYSTEM_PROMPT = """You are a data analyst assistant for a SQLite database. Users ask questions in natural language (Chinese), and you MUST query the database to find answers.

## ABSOLUTE RULES (no exceptions)

1. **You MUST always call at least one SQL tool** for any user question that mentions data, sales, products, users, cities, categories, trends, statistics, rankings, or counts. Do NOT answer directly without querying.
2. **You MUST follow this exact sequence**:
   - Step 1: Call `sql_db_list_tables` to see what tables exist
   - Step 2: Call `sql_db_schema` for the relevant table(s)
   - Step 3: Generate a COMPLETE SQL query. The SELECT clause MUST include EVERY field the user asked for.
   - Step 4: Call `sql_db_query_checker` to validate the SQL
   - Step 5: Call `sql_db_query` to execute
   - Step 6: Summarize the results in Chinese (under 200 chars)
3. **Only generate SELECT queries**. Never UPDATE/DELETE/INSERT/DROP.
4. **Table and column names MUST exactly match** what you saw in the schema output.
5. **If a tool returns an error**, analyze and retry (max 3 times). Never give up after a single failure.
6. **Your final answer MUST be based on the SQL query result**, not on your prior knowledge.

## Field mapping (zh → en)
- 姓名/名字/名称 → name
- 城市/所在地 → city
- 年龄 → age
- 注册日期 → signup_date
- 类别/分类 → category
- 价格 → price
- 销量/数量/金额 → amount / quantity

## Few-shot examples

User: 查询商品销售额
→ sql_db_list_tables → sql_db_schema(orders, products) → SELECT SUM(amount) FROM orders; → summary in Chinese

User: 查询各类商品销售额
→ sql_db_list_tables → sql_db_schema(orders, products) → SELECT p.category, SUM(o.amount) AS total FROM products p JOIN orders o ON p.id = o.product_id GROUP BY p.category ORDER BY total DESC; → summary in Chinese

User: 统计每个城市的用户数
→ sql_db_list_tables → sql_db_schema(users) → SELECT city, COUNT(*) AS cnt FROM users GROUP BY city; → summary in Chinese

User: 本月卖了多少商品
→ sql_db_list_tables → sql_db_schema(orders) → SELECT SUM(quantity) FROM orders WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now'); → summary in Chinese

REMINDER: If the user asks about any data, you MUST execute SQL. Never respond with a greeting or "how can I help" without first querying the database.
"""


def build_nl2sql_agent(db: AsyncSession):
    """构造 NL2SQL Agent"""
    llm = get_qwen3_chat_model(temperature=0.0, streaming=False)
    tools = make_sql_tools(db)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent


# ============================================================
# 4. 同步执行入口（非流式）
# ============================================================
def run_nl2sql_sync(
    db: AsyncSession,
    question: str,
    history_messages: list[BaseMessage] | None = None,
) -> dict:
    """
    同步执行 NL2SQL，返回结构化结果

    Returns:
        {
          "answer": "...",         # 最终自然语言回答
          "sql": "...",             # 最后一次生成的 SQL
          "chart": {...} | None,    # 从 SQL 结果生成的 ChartData
          "tool_calls": [...],      # 所有工具调用
          "usage": {...},           # token 统计（最后一次 AIMessage）
          "messages": [...]         # 完整 messages 历史（用于持久化）
        }
    """
    agent = build_nl2sql_agent(db)

    # 构造输入：可选历史
    msgs = []
    if history_messages:
        msgs.extend(history_messages)
    msgs.append(HumanMessage(content=question))

    result = agent.invoke({"messages": msgs})
    messages = result.get("messages", [])

    # ============================================================
    # 守卫（NL2SQL-35 稳定性）：若 LLM 没调过 sql_db_query，强制 retry 一次
    # ============================================================
    if not _has_called_sql_query(messages):
        print("[nl2sql] guard: 第一次未调 sql_db_query，强制重试")
        # 注入一条 HumanMessage 强制重做
        retry_msgs = list(messages) + [
            HumanMessage(content="[系统提示] 你的上一次回答没有查询数据库。请重新执行：先调用 sql_db_list_tables，再依次调用 sql_db_schema / sql_db_query_checker / sql_db_query。**必须调用 sql_db_query 才能返回结果。**")
        ]
        result = agent.invoke({"messages": retry_msgs})
        messages = result.get("messages", [])

    # 找最后一条 AIMessage → final answer
    final_ai = None
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            final_ai = m
            break

    # 收集所有 tool_calls 和 SQL
    all_tool_calls = []
    last_sql = None
    sql_result = None  # (columns, rows)

    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                tc_dict = {
                    "name": tc.get("name") if isinstance(tc, dict) else tc.name,
                    "id": tc.get("id") if isinstance(tc, dict) else tc.id,
                    "args": tc.get("args") if isinstance(tc, dict) else tc.args,
                }
                all_tool_calls.append(tc_dict)
                if tc_dict["name"] == "sql_db_query" and isinstance(tc_dict["args"], dict):
                    last_sql = tc_dict["args"].get("query")
        elif isinstance(m, ToolMessage):
            # 抓 sql_db_query 的结果用于生成图表
            if m.name == "sql_db_query" and m.status == "success":
                sql_result = m.content

    # 尝试从 sql_result 解析为 (columns, rows) 以生成图表
    chart_data = None
    if sql_result and last_sql:
        try:
            columns, rows = _parse_sql_tool_output(sql_result)
            if columns and rows:
                chart_data = build_chart(columns, rows, title=last_sql)
        except Exception:
            pass

    # 取最后一次 AIMessage 的 usage
    usage = {}
    if final_ai:
        usage = extract_usage(final_ai)

    return {
        "answer": final_ai.content if final_ai else "(无回答)",
        "sql": last_sql,
        "chart": chart_data,
        "tool_calls": all_tool_calls,
        "usage": usage,
        "messages": [m for m in messages if isinstance(m, (HumanMessage, AIMessage))],
    }


# ============================================================
# 5. 辅助
# ============================================================
def _has_called_sql_query(messages: list) -> bool:
    """检测整个消息历史中是否调过 sql_db_query 工具（NL2SQL-35 守卫用）"""
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            for tc in m.tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else tc.name
                if name == "sql_db_query":
                    return True
    return False


def _parse_sql_tool_output(content: str) -> tuple[list[str], list[list]]:
    """解析 'Columns: [...]\\nRows:\\n[...]...\\n' 格式"""
    import ast
    lines = content.split("\n")
    if not lines or not lines[0].startswith("Columns:"):
        return [], []
    try:
        cols = ast.literal_eval(lines[0][len("Columns:"):].strip())
    except Exception:
        return [], []
    # 找 Rows: 之后的所有行（list literal）
    rows_text = []
    in_rows = False
    for l in lines[1:]:
        if l.strip() == "Rows:":
            in_rows = True
            continue
        if in_rows and l.strip():
            rows_text.append(l)
    rows = []
    for r in rows_text:
        try:
            rows.append(list(ast.literal_eval(r)))
        except Exception:
            continue
    return cols, rows
