# -*- coding: utf-8 -*-
"""探测 App 端 favorite/detail/comment 接口的游客态可行性
若全部通过 => P2 五个核心接口 100% 游客通道，主号彻底退出生产
"""
import io
import sys
import time

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from collects_client import CollectsClient, DEVICE_PARAMS, IID, DEVICE_ID, CDID, KLINK, HOST, UA_OKHTTP

import requests

# 游客会话
g = CollectsClient(guest=True)
print("游客 cookie 字段:", sorted(c.split("=")[0] for c in g.cookie.split("; ")))

# 已知公开用户（小满）与已知视频
SEC = "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"
AID = None
try:
    items, meta = g.fetch_all(SEC, max_pages=1, sleep_range=None)
    print("小满收藏首页:", len(items), "meta:", meta)
    if items:
        AID = items[0]["aweme_id"]
        print("测试视频:", AID)
except Exception as e:
    print("预取失败:", type(e).__name__, str(e)[:150])


def build(path, params_extra):
    params = dict(params_extra)
    params.update(DEVICE_PARAMS)
    params.update({"klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
                   "_rticket": str(int(time.time() * 1000)), "ts": str(int(time.time())), "cdid": CDID})
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{HOST}{path}?{q}"


def probe(name, path, params_extra, extract):
    url = build(path, params_extra)
    hdrs = {"User-Agent": UA_OKHTTP, "Cookie": g.cookie}
    try:
        r = requests.get(url, headers=hdrs, timeout=20, verify=False)
        j = r.json()
        st = j.get("status_code")
        data = extract(j)
        print(f"[{name}] status={st} {data}")
        return st == 0
    except Exception as e:
        print(f"[{name}] ERR {type(e).__name__} {str(e)[:120]}")
        return False


# 1. favorite 接口（他人喜欢列表）
if SEC:
    ok1 = probe("favorite", "/aweme/v1/aweme/favorite/", {
        "user_id": "", "sec_user_id": SEC, "max_cursor": "0", "count": "20",
        "user_avatar_shrink": "96_96", "video_cover_shrink": "248_330",
    }, lambda j: f"n={len(j.get('aweme_list') or [])} has_more={j.get('has_more')}")

# 2. detail 接口
if AID:
    ok2 = probe("detail", "/aweme/v1/aweme/detail/", {
        "aweme_id": AID,
    }, lambda j: f"desc={str((j.get('aweme_detail') or {}).get('desc'))[:30]}")

    # 3. comment 接口
    ok3 = probe("comment", "/aweme/v1/comment/list/", {
        "aweme_id": AID, "cursor": "0", "count": "20",
    }, lambda j: f"n={len(j.get('comments') or [])} total={j.get('total')}")

print("\n== 结论 ==")
print("favorite 游客可用:", locals().get("ok1", False))
print("detail 游客可用:", locals().get("ok2", False))
print("comment 游客可用:", locals().get("ok3", False))
