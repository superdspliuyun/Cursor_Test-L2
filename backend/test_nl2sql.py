"""
NL2SQL 端到端实测脚本
=====================
目的：基于已实测的 Qwen3 + LangChain v1 create_agent 跑通 NL2SQL 全流程，
打印每一步消息的**实际字段**和**实际参数**，为 Phase 3 p3-nl2sql 编码提供真实数据。

流程：
  1. 准备一个内存 SQLite 测试库（含 3 张表：users / orders / products）
  2. 定义 4 个官方 SQL @tool（sql_db_list_tables / sql_db_schema / sql_db_query / sql_db_query_checker）
  3. create_agent() 构造 NL2SQL Agent
  4. 用一个自然语言问题驱动它
  5. 完整打印 agent.stream() / agent.invoke() 的 messages 列表
     重点看：
       - AIMessage.tool_calls[].name / .args / .id
       - ToolMessage.content（SQL 执行结果）
       - 最后 AIMessage.content（自然语言回答）
       - response_metadata（finish_reason / token_usage）

运行：python test_nl2sql.py
"""
import os
import sys
import time
import sqlite3
from pathlib import Path
from pprint import pformat

# 从 .env 读取（项目根目录 backend/.env），禁止把真实 key 硬编码到代码里
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass

API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).strip()
MODEL = os.getenv("QWEN_MODEL", "qwen3-max").strip()

if not API_KEY or API_KEY == "your_api_key_here":
    sys.stderr.write(
        "[!] 未检测到 DASHSCOPE_API_KEY。请在 backend/.env 中设置后再运行。\n"
    )


# ============================================================
# 0. 测试数据库
# ============================================================
def setup_db() -> str:
    """建一个内存 SQLite 测试库，返回 DB 文件路径（agent 用 aiosqlite）"""
    db_path = "_nl2sql_test.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        city TEXT,
        signup_date TEXT,
        age INTEGER
    );

    CREATE TABLE products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        price REAL,
        stock INTEGER
    );

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        product_id INTEGER REFERENCES products(id),
        quantity INTEGER,
        amount REAL,
        order_date TEXT,
        status TEXT
    );

    INSERT INTO users VALUES
        (1, '张三', '北京', '2024-01-15', 28),
        (2, '李四', '上海', '2024-03-22', 35),
        (3, '王五', '北京', '2024-06-10', 42),
        (4, '赵六', '深圳', '2024-08-05', 30),
        (5, '钱七', '广州', '2024-11-20', 25);

    INSERT INTO products VALUES
        (1, 'iPhone 15', '电子产品', 7999.0, 100),
        (2, '华为 Mate60', '电子产品', 6999.0, 80),
        (3, 'Nike 跑鞋', '服装', 899.0, 200),
        (4, '美的电饭煲', '家居', 399.0, 150),
        (5, 'SK-II 神仙水', '美妆', 1899.0, 60);

    INSERT INTO orders VALUES
        (1, 1, 1, 1, 7999.0, '2024-12-01', 'completed'),
        (2, 1, 3, 2, 1798.0, '2024-12-05', 'completed'),
        (3, 2, 2, 1, 6999.0, '2024-12-10', 'completed'),
        (4, 3, 1, 1, 7999.0, '2024-12-15', 'completed'),
        (5, 3, 5, 2, 3798.0, '2024-12-20', 'completed'),
        (6, 4, 4, 3, 1197.0, '2024-12-25', 'pending'),
        (7, 5, 1, 1, 7999.0, '2025-01-05', 'completed'),
        (8, 2, 3, 1, 899.0,   '2025-01-10', 'completed');
    """)
    conn.commit()
    conn.close()
    return db_path


# ============================================================
# 1. 4 个 SQL 工具（严格按 ADR-003 / docs-langchain MCP 官方原名）
# ============================================================
from langchain.tools import tool
import json


def _conn():
    return sqlite3.connect("_nl2sql_test.db")


@tool
def sql_db_list_tables() -> str:
    """List all tables available in the database. Input is an empty string, output is a comma-separated list of tables."""
    print("\n>>> [TOOL CALL] sql_db_list_tables()")
    c = _conn()
    cur = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    c.close()
    result = ", ".join(tables)
    print(f"<<< [TOOL RESULT] {result!r}")
    return result


@tool
def sql_db_schema(table_names: str) -> str:
    """Get the schema and sample rows for the specified tables. Input is a comma-separated list of table names. Always call sql_db_list_tables first to confirm table names."""
    print(f"\n>>> [TOOL CALL] sql_db_schema({table_names!r})")
    c = _conn()
    names = [n.strip() for n in table_names.split(",") if n.strip()]
    out = []
    for name in names:
        cur = c.execute(f"SELECT sql FROM sqlite_master WHERE name=?", (name,))
        row = cur.fetchone()
        ddl = row[0] if row else "(no DDL)"
        cur = c.execute(f"SELECT * FROM {name} LIMIT 3")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        out.append(f"Table: {name}\nDDL: {ddl}\nColumns: {cols}\nSample rows:\n" +
                   "\n".join(str(r) for r in rows))
    c.close()
    result = "\n\n".join(out)
    print(f"<<< [TOOL RESULT] (前 200 字) {result[:200]!r}...")
    return result


@tool
def sql_db_query(query: str) -> str:
    """Execute a SQL query against the database. Input is a detailed and correct SQL query, output is the result. If you encounter an issue with Unknown column, use sql_db_schema first."""
    print(f"\n>>> [TOOL CALL] sql_db_query({query!r})")
    try:
        c = _conn()
        cur = c.execute(query)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            result = f"Columns: {cols}\nRows:\n" + "\n".join(str(r) for r in rows)
        else:
            result = f"OK. rows_affected: {cur.rowcount}"
        c.close()
    except Exception as e:
        result = f"Error: {type(e).__name__}: {e}"
    print(f"<<< [TOOL RESULT] {result[:300]!r}")
    return result


@tool
def sql_db_query_checker(query: str) -> str:
    """Use this tool to double-check if your SQL query is correct before executing it. Always use this before sql_db_query!"""
    print(f"\n>>> [TOOL CALL] sql_db_query_checker({query!r})")
    # 简化：只做语法解析 + 表名存在性检查
    try:
        c = _conn()
        # 提取可能涉及的表名（粗略）
        upper = query.upper()
        cur = c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        valid = {r[0] for r in cur.fetchall()}
        # 拼一个简单的 EXPLAIN 试探
        c.execute(f"EXPLAIN {query}")
        result = f"OK. Query parsed successfully. Available tables: {sorted(valid)}"
    except Exception as e:
        result = f"Error: {type(e).__name__}: {e}"
    print(f"<<< [TOOL RESULT] {result!r}")
    return result


# ============================================================
# 2. LLM + Agent
# ============================================================
def build_agent():
    from langchain_openai import ChatOpenAI
    from langchain.agents import create_agent

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0.2,
    )

    system_prompt = """你是一个数据分析助手。
请用以下步骤回答用户的业务问题：
1. 先调用 sql_db_list_tables 列出所有表
2. 再调用 sql_db_schema 取得相关表的结构
3. 生成 SQL
4. 用 sql_db_query_checker 自检
5. 用 sql_db_query 执行
6. 基于结果用中文自然语言总结

可用表：users（用户）/ products（商品）/ orders（订单）
注意：orders.user_id -> users.id, orders.product_id -> products.id"""

    agent = create_agent(
        model=llm,
        tools=[sql_db_list_tables, sql_db_schema, sql_db_query, sql_db_query_checker, sql_db_query],
        system_prompt=system_prompt,
    )
    return agent


# ============================================================
# 3. 字段打印工具
# ============================================================
def dump_message(msg, idx):
    print(f"\n{'=' * 60}")
    print(f"  messages[{idx}] type={type(msg).__name__}")
    print(f"{'=' * 60}")

    if hasattr(msg, "type"):
        print(f"  .type = {msg.type!r}")
    if hasattr(msg, "name") and msg.name:
        print(f"  .name = {msg.name!r}")
    if hasattr(msg, "id") and msg.id:
        print(f"  .id = {msg.id!r}")
    if hasattr(msg, "content"):
        content_preview = repr(msg.content)
        if len(content_preview) > 400:
            content_preview = content_preview[:400] + "..."
        print(f"  .content = {content_preview}")

    # ToolMessage
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        print(f"  .tool_call_id = {msg.tool_call_id!r}")
    if hasattr(msg, "status"):
        print(f"  .status = {msg.status!r}")

    # AIMessage 专属
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        print(f"  .tool_calls (list of {len(msg.tool_calls)}):")
        for i, tc in enumerate(msg.tool_calls):
            print(f"    [{i}]")
            print(f"      .name = {tc.get('name') if isinstance(tc, dict) else tc.name!r}")
            print(f"      .id = {tc.get('id') if isinstance(tc, dict) else tc.id!r}")
            args = tc.get('args') if isinstance(tc, dict) else tc.args
            print(f"      .args = {args!r}")
            print(f"      .type = {tc.get('type') if isinstance(tc, dict) else getattr(tc, 'type', None)!r}")

    if hasattr(msg, "invalid_tool_calls") and msg.invalid_tool_calls:
        print(f"  .invalid_tool_calls = {msg.invalid_tool_calls!r}")

    if hasattr(msg, "tool_call_chunks") and msg.tool_call_chunks:
        print(f"  .tool_call_chunks = {msg.tool_call_chunks!r}")

    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
        print(f"  .usage_metadata = {dict(msg.usage_metadata) if hasattr(msg.usage_metadata, '__dict__') else msg.usage_metadata!r}")

    if hasattr(msg, "response_metadata") and msg.response_metadata:
        print(f"  .response_metadata = {msg.response_metadata!r}")
        if isinstance(msg.response_metadata, dict):
            for k, v in msg.response_metadata.items():
                print(f"    .{k} = {v!r}")

    if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
        print(f"  .additional_kwargs = {msg.additional_kwargs!r}")


# ============================================================
# 4. 端到端测试
# ============================================================
def test_invoke(agent, question: str):
    print("\n" + "#" * 70)
    print(f"  [INVOKE] 问题: {question}")
    print("#" * 70)

    t0 = time.time()
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    elapsed = time.time() - t0

    print(f"\n[总耗时] {elapsed:.2f}s")
    print(f"[result 类型] {type(result).__name__}")
    print(f"[result 顶层字段]: {list(result.keys())}")

    messages = result.get("messages", [])
    print(f"\n[messages 总数] = {len(messages)}")
    for i, m in enumerate(messages):
        dump_message(m, i)

    print(f"\n>>> 最终回答（最后一条 AIMessage）:")
    last_ai = None
    for m in reversed(messages):
        if hasattr(m, "type") and m.type == "ai":
            last_ai = m
            break
    if last_ai:
        print(f"  content: {last_ai.content!r}")


def test_stream(agent, question: str):
    print("\n" + "#" * 70)
    print(f"  [STREAM] 问题: {question}")
    print("#" * 70)

    t0 = time.time()
    step_count = 0
    final_state = None
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        step_count += 1
        msgs = chunk.get("messages", [])
        print(f"\n--- step {step_count}, messages count = {len(msgs)} ---")
        if msgs:
            last = msgs[-1]
            print(f"    last type = {type(last).__name__}")
            if hasattr(last, "type"):
                print(f"    last.type = {last.type!r}")
            if hasattr(last, "content"):
                c = repr(last.content)
                print(f"    last.content (前 200) = {c[:200]}{'...' if len(c) > 200 else ''}")
            if hasattr(last, "tool_calls") and last.tool_calls:
                print(f"    last.tool_calls = {[tc.get('name') if isinstance(tc, dict) else tc.name for tc in last.tool_calls]}")
        final_state = chunk

    elapsed = time.time() - t0
    print(f"\n[总耗时] {elapsed:.2f}s")
    print(f"[流式步数] {step_count}")


# ============================================================
# 主入口
# ============================================================
def main():
    print("[*] 建测试库...")
    db_path = setup_db()
    print(f"[*] DB path: {db_path}")

    print("[*] 构造 agent...")
    agent = build_agent()

    only = sys.argv[1] if len(sys.argv) > 1 else "all"

    if only in ("all", "1"):
        test_invoke(agent, "查询所有用户的姓名、城市和注册日期，按注册日期升序排列。")
    if only in ("all", "2"):
        test_invoke(agent, "统计每个城市的用户数量，并按数量从大到小排序。")
    if only in ("all", "3"):
        test_invoke(agent, "查询 2024 年 12 月份销售额最高的 3 个商品（包括商品名和总销售额）。")
    if only in ("all", "stream"):
        test_stream(agent, "查找所有在北京的、年龄大于 30 岁的用户。")

    # 清理
    try:
        os.remove(db_path)
    except Exception:
        pass


if __name__ == "__main__":
    main()
