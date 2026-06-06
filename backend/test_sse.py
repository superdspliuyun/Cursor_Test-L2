"""SSE 流式响应端到端测试"""
import json
import sys
import urllib.request


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8006"
    print(f"=== SSE 测试 @ {base} ===\n")

    # 1. 建 session
    req = urllib.request.Request(
        f"{base}/api/session/sessions",
        data=json.dumps({"title": "test-sse"}).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        s = json.loads(r.read())
    sid = s["id"]
    print(f"[1] session: {sid}\n")

    # 2. SSE 请求
    url = f"{base}/api/chat/chat/stream"
    payload = json.dumps({
        "session_id": sid,
        "question": "查询 2024-09 到 2025-02 每月各类别销售额，并按月份升序",
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"[2] SSE 事件流:\n")
    events = []
    with urllib.request.urlopen(req, timeout=240) as r:
        for raw in r:
            line = raw.decode("utf-8").rstrip("\n")
            if line.startswith("data: "):
                try:
                    ev = json.loads(line[6:])
                    events.append(ev)
                    et = ev.get("event", "?")
                    ed = ev.get("data", {})
                    preview = json.dumps(ed, ensure_ascii=False)[:160]
                    print(f"  [{len(events):02d}] {et:18s} {preview}")
                except Exception as e:
                    print(f"  parse err: {e}")

    print(f"\n[3] 共收到 {len(events)} 个 SSE 事件")

    # 找 final
    final = next((e for e in events if e["event"] == "final"), None)
    if final:
        ai = final["data"]["assistant_message"]
        print(f"\n[4] final answer: {ai['content'][:200]}")
        print(f"    sql:  {ai['meta'].get('sql')}")
        chart = ai["meta"].get("chart")
        if chart:
            print(f"    chart.type:  {chart.get('type')}")
            print(f"    chart.title: {chart.get('title')}")
            print(f"    labels:      {chart.get('labels')}")
            for i, ds in enumerate(chart.get("datasets", [])):
                print(f"    ds[{i}]: {ds.get('label')} = {ds.get('data')[:6]}{'...' if len(ds.get('data', [])) > 6 else ''}")


if __name__ == "__main__":
    main()
