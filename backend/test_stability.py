"""
NL2SQL 工具调用稳定性压力测试
- 跑 N 轮 × M 个短问题
- 统计 "未调工具" 的失败率
- 输出每轮的 assistant 回答 & 是否调了 SQL
"""
import json
import sys
import urllib.request


def req(url, method="GET", body=None, timeout=240):
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8006"
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    print(f"=== 工具调用稳定性压测 @ {base} ({rounds} 轮) ===\n")

    questions = [
        "查询商品销售额",
        "查询各类商品销售额",
        "看看有哪些用户",
        "统计每个城市的用户数",
        "本月卖了多少商品",
    ]

    total = 0
    fail = 0
    fail_details = []

    for ri in range(rounds):
        print(f"--- Round {ri+1}/{rounds} ---")
        for q in questions:
            total += 1
            s = req(f"{base}/api/session/sessions", method="POST", body={"title": f"stab-r{ri}"})
            sid = s["id"]
            r = req(f"{base}/api/chat/chat", method="POST", body={"session_id": sid, "question": q})
            ai = r["assistant_message"]
            meta = ai.get("meta") or {}
            tcs = meta.get("tool_calls") or []
            names = [tc.get("name") for tc in tcs]
            called_sql = "sql_db_query" in names
            mark = "✅" if called_sql else "❌"
            print(f"  {mark} Q: {q}  →  {names if names else '(NONE)'}  | ans: {ai['content'][:60]}...")
            if not called_sql:
                fail += 1
                fail_details.append((ri+1, q, ai["content"][:100]))

    print(f"\n=== 总计: {total} 题 / 失败 {fail} 题 / 失败率 {fail*100/total:.1f}% ===")
    if fail_details:
        print("\n失败明细:")
        for r, q, ans in fail_details:
            print(f"  Round {r} | {q}  →  {ans}")


if __name__ == "__main__":
    main()
