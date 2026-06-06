"""
Phase 3 端到端 smoke test
- 启动: python smoke_test.py [host:port]
- 默认 http://localhost:8006
"""
import json
import sys
import urllib.request


def req(url, method="GET", body=None, timeout=180):
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8006"
    print(f"=== Phase 3 Smoke Test @ {base} ===\n")

    # 1. health
    h = req(f"{base}/health")
    print(f"[1] health: {h['status']}  app={h['app']}  v={h['version']}")

    # 2. 列出 schema
    s = req(f"{base}/api/visualization/database/schema")
    print(f"[2] schema: {len(s['tables'])} tables")
    for t in s["tables"]:
        print(f"    - {t['name']}: {len(t['sample_rows'])} sample rows")

    # 3. 新建 session
    sess = req(f"{base}/api/session/sessions", method="POST", body={"title": "smoke-test"})
    sid = sess["id"]
    print(f"[3] session created: {sid}")

    # 4. 跑 3 个 NL2SQL 问题
    questions = [
        "查询所有用户的姓名和城市",
        "统计每个城市的用户人数，按人数降序",
        "查询销售额最高的前 3 个产品名",
    ]
    for i, q in enumerate(questions, 1):
        print(f"\n--- Q{i}: {q} ---")
        r = req(f"{base}/api/chat/chat", method="POST", body={"session_id": sid, "question": q})
        ai = r["assistant_message"]
        meta = ai["meta"]
        print(f"  answer: {ai['content']}")
        print(f"  sql:    {meta.get('sql')}")
        print(f"  chart:  {meta.get('chart')}")
        print(f"  usage:  {meta.get('usage')}")
        print(f"  tool_calls: {len(meta.get('tool_calls') or [])}")

    # 5. 列出消息
    msgs = req(f"{base}/api/session/sessions/{sid}/messages")
    print(f"\n[5] session messages: {len(msgs)}")
    for m in msgs[-3:]:
        print(f"    [{m['role']}] {m['content'][:80]}")

    # 6. rename
    r = req(f"{base}/api/session/sessions/{sid}", method="PATCH", body={"title": "重命名-smoke"})
    print(f"\n[6] renamed to: {r['title']}")

    # 7. list sessions
    lst = req(f"{base}/api/session/sessions")
    print(f"[7] total sessions: {len(lst)}")

    # 8. delete
    # request returns 204
    r = urllib.request.Request(f"{base}/api/session/sessions/{sid}", method="DELETE")
    with urllib.request.urlopen(r, timeout=5) as resp:
        print(f"[8] delete: {resp.status}")

    print("\n=== ALL SMOKE TESTS PASSED ===")


if __name__ == "__main__":
    main()
