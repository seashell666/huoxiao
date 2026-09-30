# -*- coding: utf-8 -*-
"""实测 App 端用户主页接口：profile/other 与 profile/self 带 sec_user_id"""
import requests, time, json

HOST = "https://aweme.snssdk.com"
UA_OKHTTP = "okhttp/4.9.2"
SEC = "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"  # 小满

DEVICE_PARAMS = {
    "ac": "wifi", "channel": "update", "aid": "1128", "app_name": "aweme",
    "version_code": "390700", "version_name": "39.7.0", "device_platform": "android",
    "os": "android", "ssmix": "a", "device_type": "M2011K2C", "device_brand": "Xiaomi",
    "language": "zh", "os_api": "33", "os_version": "13", "manifest_version_code": "390701",
    "resolution": "1080*2297", "dpi": "420", "update_version_code": "39709900",
    "package": "com.ss.android.ugc.aweme", "first_launch_timestamp": "1789694171",
    "last_deeplink_update_version_code": "39709900", "cpu_support64": "true",
    "host_abi": "arm64-v8a", "is_guest_mode": "0", "app_type": "normal",
    "minor_status": "0", "appTheme": "light", "is_preinstall": "0",
    "need_personal_recommend": "1", "is_android_pad": "0", "is_android_fold": "0",
}
IID = "2592007553869659"; DEVICE_ID = "2496340837271500"; CDID = "d62849b1-9c92-4c33-9ca4-8941f81768b1"
KLINK = "AAILyRJYFdxlIx2MLtxIbkJ18zx5ICEM6-PYaPYj2tkbVDyFRgUbYLlb"

s = requests.Session()
s.proxies = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}
r = s.get("https://www.douyin.com/", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36", "Referer": "https://www.douyin.com/"}, timeout=20, verify=False)
cookie = "; ".join(f"{k}={v}" for k, v in s.cookies.items())
print("游客 cookie:", cookie[:80], "...")

def build_url(path, sec):
    params = {
        "enter_from": "others_homepage", "tpsa_version": "1", "address_book_access": "2",
        "from": "0", "webcast_plugin_ready": "true", "card_partition": "0", "card_style": "0",
        "hit_ab_test": "1", "btn_in_value": "0",
        "use_profile_show_identify_auth_info": "true", "show_freq_visit_card_bubble": "1",
        "publish_video_strategy_type": "2", "sec_user_id": sec,
        "klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
        "_rticket": str(int(time.time()*1000)), "ts": str(int(time.time())), "cdid": CDID,
    }
    params.update(DEVICE_PARAMS)
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{HOST}{path}?{q}"

for path in ["/aweme/v1/user/profile/other/", "/aweme/v1/user/profile/self/", "/aweme/v1/user/"]:
    url = build_url(path, SEC)
    try:
        rr = s.get(url, headers={"User-Agent": UA_OKHTTP, "Cookie": cookie}, timeout=20, verify=False)
        j = rr.json()
        st = j.get("status_code", "?")
        user = j.get("user") or {}
        uid = user.get("uid")
        print(f"\n=== {path} -> status={st}, uid={uid} ===")
        if user:
            print("  nickname:", user.get("nickname"))
            print("  avatar:", (user.get("avatar_thumb") or {}).get("url_list", [""])[0][:80])
            print("  signature:", (user.get("signature") or "")[:40])
            print("  stats:", {k: user.get(k) for k in ["follower_count","following_count","favoriting_count","total_favorited","gender","region","birthday","user_age"]})
    except Exception as e:
        print(f"\n=== {path} -> ERR: {e}")
