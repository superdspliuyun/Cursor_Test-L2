"""
LLM 工具调用稳定性基线测试
- 跑 5 个短问题
- 看每个问题有没有调 SQL 工具
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
    print(f"=== 短问题基线 @ {base} ===\n")

    questions = [
        "查询商品销售额",
        "查询各类商品销售额",
        "看看有哪些用户",
        "统计每个城市的用户数",
        "本月卖了多少商品",
    ]

    for q in questions:
        s = req(f"{base}/api/session/sessions", method="POST", body={"title": "short-q"})
        sid = s["id"]
        r = req(f"{base}/api/chat/chat", method="POST", body={"session_id": sid, "question": q})
        ai = r["assistant_message"]
        meta = ai["meta"] or {}
        tcs = meta.get("tool_calls") or []
        names = [tc.get("name") for tc in tcs]
        print(f"Q: {q}")
        print(f"   answer: {ai['content'][:80]}...")
        print(f"   tools : {names if names else '(NONE) ❌'}")
        print(f"   sql   : {meta.get('sql') or '(none)'}")
        print()


if __name__ == "__main__":
    main()
