# -*- coding: utf-8 -*-
"""关键实验：游客 cookie + App 设备指纹头（去登录 token）能否拿 favorite/comment/post
若通过 => 生产 100% 游客可拿全部公开数据（完全符合"不登录极速"目标）
若失败 => 需备用身份通道（向用户如实报告并决策）
"""
import io
import json
import sys
import time

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from collects_client import CollectsClient, DEVICE_PARAMS, IID, DEVICE_ID, CDID, KLINK, HOST
from curl_cffi import requests

# 设备指纹头（从真机抓包固化，非登录 token）
DEVICE_HEADERS = {
    "User-Agent": "com.ss.android.ugc.aweme/390700 (Linux; U; Android 13; zh_CN; M2011K2C; Build/TKQ1.220829.002; Cronet/58.0.2991.0)",
    "Accept": "application/json",
    "Host": "aweme.snssdk.com",
    "x-bd-client-key": "988dde074930267dee6251f175a4470f1f1b25f7a87826e6bb5b1d30d82f0a8d84609486196db2930052c33d23c14e2f7ff21463cb983c77898fe100b34a3cd8",
    "x-bd-kmsv": "1",
    "x-tt-dt": "AAA6I3AF52BUISCJ2V7LASBMWY5U25XHXZSC7CHSBTZQ3AQHZU45ASW34NBB6M7BDPEADPKKDGIJ4TE3LAO2O36TU7FO4HOPXLHIYF633QBZB3HY4QNFN54CBQNWJURVVQSZTWTAFSCLLGK33AVRSFY",
}

SEC = "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"
UID = "80545599996"
AID = "7665624049695417454"

g = CollectsClient(guest=True)
guest_cookie = g.cookie
print("游客 cookie:", sorted(c.split("=")[0] for c in guest_cookie.split("; ")))

BASE_Q = ("klink_egdi=AAKgam4fWmmGF00oC1MNQ9jhYrdTlyUxEgVPzXw8w-Ksju8sCwhaN5J5"
          "&iid=2592007553869659&device_id=2496340837271500&ac=wifi&channel=update&aid=1128"
          "&app_name=aweme&version_code=390700&version_name=39.7.0&device_platform=android"
          "&os=android&ssmix=a&device_type=M2011K2C&device_brand=Xiaomi&language=zh&os_api=33"
          "&os_version=13&manifest_version_code=390701&resolution=1080*2297&dpi=420"
          "&update_version_code=39709900&package=com.ss.android.ugc.aweme"
          "&first_launch_timestamp=1789694171&last_deeplink_update_version_code=39709900"
          "&cpu_support64=true&host_abi=arm64-v8a&is_guest_mode=0&app_type=normal"
          "&minor_status=0&appTheme=light&is_preinstall=0&need_personal_recommend=1"
          "&is_android_pad=0&is_android_fold=0&cdid=d62849b1-9c92-4c33-9ca4-8941f81768b1")


def call(path, extra):
    url = f"https://aweme.snssdk.com{path}?{extra}&{BASE_Q}&_rticket={int(time.time()*1000)}&ts={int(time.time())}"
    h = dict(DEVICE_HEADERS)
    h["X-SS-REQ-TICKET"] = str(int(time.time() * 1000))
    h["activity_now_client"] = str(int(time.time() * 1000))
    h["Cookie"] = guest_cookie
    resp = requests.get(url, headers=h, impersonate="chrome", timeout=25, verify=False)
    try:
        return resp.json()
    except Exception:
        print("  非JSON:", resp.text[:150])
        return None


FULL = ("publish_video_strategy_type=2&source=0&user_avatar_shrink=96_96&video_cover_shrink=248_330"
        "&show_live_replay_strategy=1&is_order_flow=0&page_from=2&location_permission=1"
        "&familiar_collects=0&page_scene=1&post_serial_strategy=0&need_article=1&need_lvideo=1"
        "&exp_optimize=1&invalid_item_count=0&is_hiding_invalid_item=0&hotsoon_filtered_count=0"
        "&hotsoon_has_more=0")

print("\n=== 1. favorite（游客+设备头） ===")
j = call("/aweme/v1/aweme/favorite/",
         f"{FULL}&user_id={UID}&max_cursor=0&req_count=9&sec_user_id={SEC}")
if j:
    al = j.get("aweme_list") or []
    print(f"  list={len(al)} status={j.get('status_code')} has_more={j.get('has_more')}")
    for a in al[:2]:
        print("    ", a.get("aweme_id"), str(a.get("desc"))[:40])

print("\n=== 2. comment（游客+设备头） ===")
j = call("/aweme/v1/comment/list/",
         f"aweme_id={AID}&cursor=0&count=20&comment_style=0&filter=0&scene=0")
if j:
    cm = j.get("comments") or []
    print(f"  comments={len(cm)} total={j.get('total')} status={j.get('status_code')}")
    for c in cm[:2]:
        print("    ", str(c.get("text"))[:30])

print("\n=== 3. post（游客+设备头） ===")
j = call("/aweme/v1/aweme/post/",
         f"sec_user_id={SEC}&user_id={UID}&max_cursor=0&count=20&is_filter=0")
if j:
    al = j.get("aweme_list") or []
    print(f"  list={len(al)} status={j.get('status_code')} has_more={j.get('has_more')}")
    for a in al[:2]:
        print("    ", a.get("aweme_id"), str(a.get("desc"))[:40])

print("\n=== 4. following（游客+设备头） ===")
j = call("/aweme/v1/user/following/list/",
         f"source=0&user_id={UID}&sec_user_id={SEC}&max_time=0&count=20&offset=0&source_type=2&gps_access=1&address_book_access=1")
if j:
    fl = j.get("followings") or []
    print(f"  list={len(fl)} status={j.get('status_code')} has_more={j.get('has_more')}")
    for u in fl[:2]:
        print("    ", u.get("nickname"), u.get("sec_uid", "")[:20])
