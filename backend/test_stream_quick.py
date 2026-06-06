"""快速复现浏览器场景：会话存在 + 短问题，验证 SSE 是否能起来"""
import json
import urllib.request
import sys

sid = "ace6c736c9594933a1b06692e393c4e5"  # 刚建的
url = "http://localhost:8006/api/chat/chat/stream"
payload = json.dumps({"session_id": sid, "question": "查询商品销售额"}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(url, data=payload,
                              headers={"Content-Type": "application/json"}, method="POST")
print(f"POST {url} session={sid}")
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f"status: {r.status}")
        n = 0
        for raw in r:
            n += 1
            line = raw.decode("utf-8").rstrip()
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                print(f"  ev#{n}: {ev.get('event')} - {json.dumps(ev.get('data'), ensure_ascii=False)[:120]}")
                if ev.get("event") == "end":
                    break
            if n > 30:
                break
except Exception as e:
    print(f"ERR: {e}")
