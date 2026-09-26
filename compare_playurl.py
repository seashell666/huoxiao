# -*- coding: utf-8 -*-
"""对比：主号 webSign detail 直链 vs 游客 detail 直链（下载可达性）"""
import io
import os
import sys

sys.path.insert(0, r"F:\D\20-火枭\参考-DouYin_Spider")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"

import requests
from builder.auth import DouyinAuth
from builder.header import HeaderBuilder, HeaderType
from builder.params import Params
from utils.secsdk_web_sign import sign_url
from utils import http_client

sys.path.insert(0, r"F:\D\Android-Hook\服务")
from huoxiao_client import HuoxiaoClient

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
DLH = {"User-Agent": UA, "Referer": "https://www.douyin.com/", "Accept": "*/*"}
AID = "7665624049695417454"

# 1. 游客直链
c = HuoxiaoClient()
d, meta = c.guest.get_detail(AID)
guest_url = d.get("play_url") or ""
print("游客 quality:", d.get("quality"))

# 2. 主号 webSign 直链
vault = r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\douyin-cookie-vault\assets\douyin_cookie.txt"
auth = DouyinAuth.from_cookie(io.open(vault, encoding="utf-8").read().strip())
headers = HeaderBuilder.build(HeaderType.GET)
url = f"https://www.douyin.com/video/{AID}"
headers.set_referer(url)
headers.with_uifid(auth)
params = Params()
for k, v in {"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web", "aweme_id": AID}.items():
    params.add_param(k, v)
params.with_platform(round_trip_time="0")
params.with_web_id(auth=auth, url=url)
params.with_uifid(auth)
params.with_verify_fp(auth)
params.add_param("msToken", auth.msToken)
params.with_a_bogus()
raw = params.signed_url("https://www.douyin.com/aweme/v1/web/aweme/detail/", auth)
uifid = None
for p in raw.split("?", 1)[1].split("&"):
    if p.startswith("uifid="):
        uifid = p.split("=", 1)[1]
        break
signed = sign_url(raw, uifid=uifid)
r = http_client.get(signed, headers=headers.get(), cookies=auth.cookie, verify=False, timeout=25)
aw = r.json().get("aweme_detail") or {}
vid = aw.get("video") or {}
main_url = None
for br in vid.get("bit_rate") or []:
    if "1080" in str(br.get("gear_name") or ""):
        main_url = ((br.get("play_addr") or {}).get("url_list") or [None])[0]
        break
if not main_url:
    main_url = ((vid.get("download_addr") or {}).get("url_list") or [None])[0]
print("主号 quality:", [str(b.get("gear_name")) for b in (vid.get("bit_rate") or [])][:3])

for tag, u in (("guest", guest_url), ("main", main_url)):
    try:
        resp = requests.get(u, headers=DLH, timeout=30, stream=True, verify=False)
        head = next(resp.iter_content(16), b"")
        print(f"[{tag}] http={resp.status_code} head={head[:8].hex()} is_mp4={head[4:8] == b'ftyp'}")
    except Exception as e:
        print(f"[{tag}] ERR {type(e).__name__}: {str(e)[:100]}")
