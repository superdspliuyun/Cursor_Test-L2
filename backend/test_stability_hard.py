"""
更刁钻的稳定性压测
- 5 轮 × 8 个更短/更模糊的问题
- 验证守卫路径（若 LLM 第一次没调 sql_db_query，第二次重试必须调）
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
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print(f"=== 硬核压测 @ {base} ({rounds} 轮 × 8 题) ===\n")

    questions = [
        "你好",                          # 模糊
        "你能做什么",                    # 元问题
        "销量",                          # 单字
        "总数",                          # 单字
        "趋势",                          # 单字
        "?",                             # 标点
        "最近 30 天",                    # 时间
        "本月数据",                      # 模糊
    ]

    total = 0
    fail = 0
    fail_details = []

    for ri in range(rounds):
        print(f"--- Round {ri+1}/{rounds} ---")
        for q in questions:
            total += 1
            s = req(f"{base}/api/session/sessions", method="POST", body={"title": f"hard-r{ri}"})
            sid = s["id"]
            r = req(f"{base}/api/chat/chat", method="POST", body={"session_id": sid, "question": q})
            ai = r["assistant_message"]
            meta = ai.get("meta") or {}
            tcs = meta.get("tool_calls") or []
            names = [tc.get("name") for tc in tcs]
            called_sql = "sql_db_query" in names
            mark = "✅" if called_sql else "❌"
            print(f"  {mark} Q: {q!r:20s} → {names if names else '(NONE)'}  | ans: {ai['content'][:50]}...")
            if not called_sql:
                fail += 1
                fail_details.append((ri+1, q, ai["content"][:100]))

    print(f"\n=== 总计: {total} 题 / 失败 {fail} 题 / 失败率 {fail*100/total:.1f}% ===")
    if fail_details:
        print("\n失败明细:")
        for r, q, ans in fail_details:
            print(f"  Round {r} | {q!r}  →  {ans}")


if __name__ == "__main__":
    main()
