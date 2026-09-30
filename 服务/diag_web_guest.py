# -*- coding: utf-8 -*-
"""诊断 Web 匿名请求的响应内容"""
import os
import sys
import time

sys.path.insert(0, r"F:\D\20-火枭\参考-DouYin_Spider")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"

import requests
from builder.auth import DouyinAuth
from builder.header import HeaderBuilder, HeaderType
from builder.params import Params
from utils.secsdk_web_sign import sign_url

WEB = "https://www.douyin.com"
auth = DouyinAuth()
print("匿名 auth, msToken:", bool(getattr(auth, "msToken", None)))

headers = HeaderBuilder.build(HeaderType.GET)
ref = f"{WEB}/user/MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"
headers.set_referer(ref)
p = Params()
for k, v in {"sec_user_id": "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw",
             "max_cursor": 0, "count": 5}.items():
    p.add_param(k, v)
p.add_param("device_platform", "webapp")
p.add_param("aid", "6383")
p.add_param("channel", "channel_pc_web")
p.with_platform(round_trip_time="0")
try:
    p.with_web_id(auth, ref)
except Exception as e:
    print("web_id err:", e)
p.add_param("msToken", auth.msToken if getattr(auth, "msToken", None) else "")
try:
    p.with_a_bogus()
except Exception as e:
    print("a_bogus err:", e)
url = f"{WEB}/aweme/v1/web/aweme/favorite/?{p.get()}"
url2 = sign_url(url)

for tag, u in (("signed", url2), ("raw", url)):
    try:
        r = requests.get(u, headers=headers.get(), timeout=20, verify=False)
        print(f"[{tag}] http={r.status_code} ct={r.headers.get('content-type','')[:40]} len={len(r.text)}")
        print(f"  head={r.text[:200]!r}")
    except Exception as e:
        print(f"[{tag}] ERR {type(e).__name__}: {str(e)[:100]}")
    time.sleep(6)
