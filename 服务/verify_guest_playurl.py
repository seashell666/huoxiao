# -*- coding: utf-8 -*-
"""验证游客 detail 能否拿到 1080p 无水印直链（P3 下载服务前提）"""
import io
import json
import sys

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from huoxiao_client import HuoxiaoClient

c = HuoxiaoClient()
aid = "7665624049695417454"
d, meta = c.guest.get_detail(aid)
print("meta:", meta)
if not d:
    print("detail 失败")
    sys.exit(1)
print("desc:", d.get("desc", "")[:40])
print("quality:", d.get("quality"))
pu = d.get("play_url") or ""
print("play_url head:", pu[:120])
print("width x height:", d.get("width"), "x", d.get("height"))

# 验证直链可下载（HEAD/前 16 字节）
if pu:
    import requests
    try:
        r = requests.get(pu, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.douyin.com/"},
                         timeout=30, stream=True, verify=False)
        head = next(r.iter_content(16), b"")
        print("直链 http:", r.status_code, "前16字节:", head[:8].hex(), "len>0:", len(head) > 0)
    except Exception as e:
        print("直链测试 ERR:", type(e).__name__, str(e)[:100])
