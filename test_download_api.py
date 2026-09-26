# -*- coding: utf-8 -*-
"""直接测试下载任务接口"""
import json
import sys
import time

import requests

BASE = "http://127.0.0.1:8100"
H = {"X-Api-Key": "huoxiao-2026", "Content-Type": "application/json"}

r = requests.post(f"{BASE}/v1/download", headers=H,
                  data=json.dumps({"aweme_ids": ["7665624049695417454", "7336424682740886282"]}),
                  timeout=15)
print("POST:", r.status_code, r.text[:300])
try:
    tid = r.json()["data"]["task_id"]
except Exception:
    print("no task id")
    sys.exit(1)

for i in range(8):
    time.sleep(5)
    t = requests.get(f"{BASE}/v1/task/{tid}", headers=H, timeout=10)
    d = t.json()["data"]
    print(f"poll{i}: status={d['status']} done={d['done_count']} ok={d['ok_count']} fail={d['fail_count']}")
    if d["status"] in ("done", "failed"):
        for k, v in d["items"].items():
            print("  ", k, v.get("status"), v.get("size"), v.get("gear"), v.get("err", ""))
        break
