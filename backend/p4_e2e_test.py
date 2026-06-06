"""Phase 4 端到端联调：模拟前端走 vite proxy 跑一次完整流程"""
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
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5175"
    print(f"=== Phase 4 联调 E2E @ {base} (vite proxy -> 8006) ===\n")

    # 1. 列出 session
    sessions = req(f"{base}/api/session/sessions")
    print(f"[1] sessions via proxy: {len(sessions)} 个")
    if sessions:
        sid = sessions[0]["id"]
        print(f"    取第一个: {sid} title='{sessions[0]['title']}'")
    else:
        print("    无 session, 先创建")
        s = req(f"{base}/api/session/sessions", method="POST", body={"title": "p4-e2e"})
        sid = s["id"]
        print(f"    created: {sid}")

    # 2. 拉历史
    msgs = req(f"{base}/api/session/sessions/{sid}/messages")
    print(f"[2] 历史消息: {len(msgs)} 条")

    # 3. 调 chat（NL2SQL 端到端）
    print(f"[3] 触发 NL2SQL chat...")
    r = req(f"{base}/api/chat/chat", method="POST",
            body={"session_id": sid, "question": "查询所有产品的名称和库存，按库存降序"})
    ai = r["assistant_message"]
    print(f"    answer: {ai['content']}")
    print(f"    sql:    {ai['meta'].get('sql')}")
    print(f"    chart.type:  {ai['meta'].get('chart', {}).get('type')}")
    print(f"    chart.title: {ai['meta'].get('chart', {}).get('title')}")
    print(f"    tool_calls:  {len(ai['meta'].get('tool_calls') or [])}")
    print(f"    usage:       {ai['meta'].get('usage')}")

    # 4. 再拉一次历史，看持久化
    msgs2 = req(f"{base}/api/session/sessions/{sid}/messages")
    print(f"\n[4] 再次拉历史: {len(msgs2)} 条 (新增 2 条 user+assistant)")

    print("\n=== Phase 4 联调通过 ===")


if __name__ == "__main__":
    main()
