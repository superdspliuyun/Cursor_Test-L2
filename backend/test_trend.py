"""
销售趋势测试：按产品类别统计各月的销售额，按销售额排序
目标问题：请查询各个产品类别的销售趋势，并按照销售额排序
"""
import json
import urllib.request
import sys


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
    print(f"=== 销售趋势测试 @ {base} ===\n")

    # 1. 新建会话（不污染现有数据）
    s = req(f"{base}/api/session/sessions", method="POST", body={"title": "test-trend"})
    sid = s["id"]
    print(f"[1] session: {sid}")

    # 2. 提问
    q = "请查询各个产品类别的销售趋势，并按照销售额排序"
    print(f"[2] question: {q}\n")
    r = req(f"{base}/api/chat/chat", method="POST", body={"session_id": sid, "question": q})
    ai = r["assistant_message"]
    meta = ai["meta"]

    print(f"[3] answer: {ai['content']}\n")
    print(f"[4] sql: {meta.get('sql')}\n")
    print(f"[5] chart:")
    chart = meta.get("chart")
    if chart:
        print(f"    type:     {chart.get('type')}")
        print(f"    title:    {chart.get('title')}")
        print(f"    labels:   {chart.get('labels')}")
        for i, ds in enumerate(chart.get("datasets", [])):
            print(f"    ds[{i}].label:    {ds.get('label')}")
            print(f"    ds[{i}].data:     {ds.get('data')}")
            print(f"    ds[{i}].bgColor:  {ds.get('backgroundColor', '(none)')}")
        if chart.get("tableData"):
            print(f"    tableData ({len(chart['tableData'])} 行):")
            for row in chart["tableData"][:5]:
                print(f"      {row}")
    else:
        print("    (无图表)")

    print(f"\n[6] tool_calls: {len(meta.get('tool_calls') or [])}")
    for tc in meta.get("tool_calls") or []:
        print(f"    - {tc.get('name')}({list((tc.get('args') or {}).keys())})")

    print(f"\n[7] usage: {meta.get('usage')}")


if __name__ == "__main__":
    main()
