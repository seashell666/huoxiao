# -*- coding: utf-8 -*-
"""探测 favorite/comment 空数据原因：调整参数 + 看完整响应结构"""
import io
import json
import sys
import time

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from collects_client import CollectsClient, DEVICE_PARAMS, IID, DEVICE_ID, CDID, KLINK, HOST, UA_OKHTTP
import requests

# 查小满公开性
m = json.load(io.open(r"F:\D\Android-Hook\输出数据\privacy_matrix_v4.json", encoding="utf-8"))
rows = m.get("rows") or []
for r in rows:
    if r.get("nickname") == "小满":
        print("小满:", json.dumps(r, ensure_ascii=False)[:600])
        break

g = CollectsClient(guest=True)
AID = "7665624049695417454"  # 刚才拿到的视频


def raw_req(name, path, params_extra, print_raw=False):
    params = dict(params_extra)
    params.update(DEVICE_PARAMS)
    params.update({"klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
                   "_rticket": str(int(time.time() * 1000)), "ts": str(int(time.time())), "cdid": CDID})
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{HOST}{path}?{q}"
    r = requests.get(url, headers={"User-Agent": UA_OKHTTP, "Cookie": g.cookie}, timeout=20, verify=False)
    j = r.json()
    print(f"[{name}] keys={list(j.keys())[:12]}")
    if print_raw:
        print(json.dumps(j, ensure_ascii=False)[:1500])
    return j


# favorite 带完整响应
j1 = raw_req("favorite-full", "/aweme/v1/aweme/favorite/", {
    "user_id": "", "sec_user_id": "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw",
    "max_cursor": "0", "count": "20", "source": "profile",
}, print_raw=True)

# comment 带完整响应
j2 = raw_req("comment-full", "/aweme/v1/comment/list/", {
    "aweme_id": AID, "cursor": "0", "count": "20",
}, print_raw=True)
