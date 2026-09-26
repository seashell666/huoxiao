# -*- coding: utf-8 -*-
"""直链 403 诊断：完整 UA 重试"""
import io
import sys

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from huoxiao_client import HuoxiaoClient
import requests

c = HuoxiaoClient()
d, meta = c.guest.get_detail("7665624049695417454")
pu = d.get("play_url") or ""
print("url:", pu[:100])

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
for tag, hd in (
    ("full-ua+ref", {"User-Agent": UA, "Referer": "https://www.douyin.com/", "Accept": "*/*"}),
    ("full-ua+ref-video", {"User-Agent": UA, "Referer": "https://www.douyin.com/video/7665624049695417454", "Accept": "*/*"}),
):
    try:
        r = requests.get(pu, headers=hd, timeout=30, stream=True, verify=False)
        head = next(r.iter_content(16), b"")
        print(f"[{tag}] http={r.status_code} head={head[:8].hex()}")
    except Exception as e:
        print(f"[{tag}] ERR {type(e).__name__}: {str(e)[:100]}")
