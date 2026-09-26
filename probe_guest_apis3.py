# -*- coding: utf-8 -*-
"""App 端 favorite/comment/post 游客态探测（完整参数 + user_id）"""
import io
import json
import sys
import time

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from collects_client import CollectsClient, DEVICE_PARAMS, IID, DEVICE_ID, CDID, KLINK, HOST, UA_OKHTTP
import requests

# 小满 uid
m = json.load(io.open(r"F:\D\Android-Hook\输出数据\privacy_matrix_v4.json", encoding="utf-8"))
rows = m.get("rows") or []
SEC = "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"
UID = ""
for r in rows:
    if r.get("sec_uid", "")[:40] == SEC[:40]:
        UID = str(r.get("uid", ""))
        print("小满 uid:", UID, "favorite:", (r.get("favorite") or {}).get("verdict"))
        break
if not UID:
    print("未找到小满 uid，退出")
    sys.exit(1)

g = CollectsClient(guest=True)
print("游客 cookie:", sorted(c.split("=")[0] for c in g.cookie.split("; ")))

FULL = ("publish_video_strategy_type=2&source=0&user_avatar_shrink=96_96&video_cover_shrink=248_330"
        "&show_live_replay_strategy=1&is_order_flow=0&page_from=2&location_permission=1"
        "&familiar_collects=0&page_scene=1&post_serial_strategy=0&need_article=1&need_lvideo=1"
        "&exp_optimize=1&invalid_item_count=0&is_hiding_invalid_item=0&hotsoon_filtered_count=0"
        "&hotsoon_has_more=0")


def build(path, extra_q):
    params = {"klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
              "_rticket": str(int(time.time() * 1000)), "ts": str(int(time.time())), "cdid": CDID}
    params.update(DEVICE_PARAMS)
    q = extra_q + "&" + "&".join(f"{k}={v}" for k, v in params.items())
    return f"{HOST}{path}?{q}"


def probe(name, path, extra_q, extract):
    url = build(path, extra_q)
    r = requests.get(url, headers={"User-Agent": UA_OKHTTP, "Cookie": g.cookie}, timeout=20, verify=False)
    try:
        j = r.json()
    except Exception:
        print(f"[{name}] 非JSON http={r.status_code} head={r.text[:120]!r}")
        return
    st = j.get("status_code")
    print(f"[{name}] status={st} {extract(j)}")
    return j


# 1. favorite 完整参数 + user_id（游客）
j = probe("favorite", "/aweme/v1/aweme/favorite/",
          f"{FULL}&user_id={UID}&max_cursor=0&req_count=9&sec_user_id={SEC}",
          lambda j: f"n={len(j.get('aweme_list') or [])} has_more={j.get('has_more')}")
if j and (j.get("aweme_list") or []):
    a = j["aweme_list"][0]
    print("  首条:", a.get("aweme_id"), str(a.get("desc"))[:40])

# 2. comment（App 端路径，完整参数）
AID = None
if j and (j.get("aweme_list") or []):
    AID = j["aweme_list"][0]["aweme_id"]
else:
    # 用已知视频
    AID = "7665624049695417454"
probe("comment", "/aweme/v1/comment/list/",
      f"aweme_id={AID}&cursor=0&count=20&comment_style=0&filter=0&scene=0",
      lambda j: f"n={len(j.get('comments') or [])} total={j.get('total')} has_more={j.get('has_more')}")

# 3. post（发布作品）
probe("post", "/aweme/v1/aweme/post/",
      f"sec_user_id={SEC}&user_id={UID}&max_cursor=0&count=20&is_filter=0",
      lambda j: f"n={len(j.get('aweme_list') or [])} has_more={j.get('has_more')}")
