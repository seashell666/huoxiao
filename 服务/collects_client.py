# -*- coding: utf-8 -*-
"""火枭采集器：App 端 listcollection（他人收藏视频列表）
双模式：
  - auth 模式：主号 cookie（带 sessionid），保号慢速
  - guest 模式：游客 cookie（HTTP 预取，无 sessionid），极速零封号风险
接口：https://aweme.snssdk.com/aweme/v1/aweme/listcollection/
发现记录：2026-09-18 夜间攻坚（listcollection Web 已死 404；collects/list 私有；
App 端接口直连成功，无需 X-Bogus，游客 cookie 亦可）
错误码：3002279 = 该用户收藏未公开（私密）
"""
import io, os, sys, time, random, datetime
import requests
import time as _t

UA_OKHTTP = "okhttp/4.9.2"
HOST = "https://aweme.snssdk.com"
API_LISTCOLLECTION = "/aweme/v1/aweme/listcollection/"

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
IID = "2592007553869659"
DEVICE_ID = "2496340837271500"
CDID = "d62849b1-9c92-4c33-9ca4-8941f81768b1"
KLINK = "AAKgam4fWmmGF00oC1MNQ9jhYrdTlyUxEgVPzXw8w-Ksju8sCwhaN5J5"


class CollectsClient:
    def __init__(self, cookie_str=None, guest=False, proxy="http://127.0.0.1:10809"):
        self.cookie = cookie_str
        self.guest = guest
        self._s = requests.Session()
        if proxy:
            self._s.proxies = {"http": proxy, "https": proxy}
        if guest:
            self._fetch_guest_cookie()

    def _fetch_guest_cookie(self):
        """HTTP 预取游客 cookie（ttwid/__ac_nonce 等，无 sessionid）"""
        r = self._s.get("https://www.douyin.com/", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        }, timeout=20, verify=False)
        parts = []
        for k, v in self._s.cookies.items():
            parts.append(f"{k}={v}")
        self.cookie = "; ".join(parts)
        return self.cookie

    def _url(self, sec, cursor, count):
        params = {
            "user_avatar_shrink": "96_96", "video_cover_shrink": "248_330",
            "need_time_list": "0", "cursor": cursor, "sec_user_id": sec, "count": count,
            "show_live_replay_strategy": "1", "is_order_flow": "0", "page_from": "2",
            "location_permission": "1", "familiar_collects": "0", "locate_item_cursor": "0",
            "klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
            "_rticket": str(int(_t.time() * 1000)), "ts": str(int(_t.time())), "cdid": CDID,
        }
        params.update(DEVICE_PARAMS)
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{HOST}{API_LISTCOLLECTION}?{q}"

    def get_page(self, sec, cursor="0", count="20"):
        url = self._url(sec, cursor, count)
        hdrs = {"User-Agent": UA_OKHTTP, "Cookie": self.cookie}
        r = self._s.get(url, headers=hdrs, timeout=20, verify=False)
        return r.json()

    def fetch_all(self, sec, max_pages=20, sleep_range=(3, 6), on_page=None):
        """翻页拿全部收藏。返回 (items, meta)
        meta: {"status": int, "closed": bool, "pages": int}
        closed=True 表示该用户收藏未公开（status=3002279）
        """
        items, cursor, pages = [], "0", 0
        while pages < max_pages:
            j = self.get_page(sec, cursor)
            st = j.get("status_code")
            if st != 0:
                return items, {"status": st, "closed": st in (3002279,), "pages": pages}
            al = j.get("aweme_list") or []
            items.extend(al)
            if on_page:
                on_page(pages + 1, len(al), j)
            if not j.get("has_more") or not al:
                break
            cursor = j.get("cursor") or str(len(items))
            pages += 1
            if sleep_range:
                time.sleep(random.uniform(*sleep_range))
        return items, {"status": 0, "closed": False, "pages": pages + 1}

    def visibility(self, sec):
        """仅判公开性（count=1 最小请求）"""
        j = self.get_page(sec, count="1")
        st = j.get("status_code")
        return {"status": st, "open": st == 0, "closed": st in (3002279,),
                "n": len(j.get("aweme_list") or [])}

    def get_page_detail(self, aid):
        """游客态视频详情（App 端 detail，已验证游客可用）"""
        params = {
            "aweme_id": aid, "klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
            "_rticket": str(int(_t.time() * 1000)), "ts": str(int(_t.time())), "cdid": CDID,
        }
        params.update(DEVICE_PARAMS)
        q = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{HOST}/aweme/v1/aweme/detail/?{q}"
        r = self._s.get(url, headers={"User-Agent": UA_OKHTTP, "Cookie": self.cookie}, timeout=20, verify=False)
        return r.json()


if __name__ == "__main__":
    # 自测
    import json
    out = r"F:\D\Android-Hook\输出数据"
    vault = r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\douyin-cookie-vault\assets\douyin_cookie.txt"
    ck = io.open(vault, encoding="utf-8").read().strip()

    print("== 登录态自测 ==")
    c1 = CollectsClient(cookie_str=ck)
    items, meta = c1.fetch_all("MS4wLjABAAAAGwq3DhDrkwOInZwmFaupVXxojEPgGM900gPF8fOwtGEAtrnXqIlMadicavJTueew", max_pages=3)
    print("主号收藏:", len(items), "meta:", meta)
    json.dump([{"aweme_id": a.get("aweme_id"), "desc": a.get("desc")} for a in items],
              io.open(os.path.join(out, "app_collects_main.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n== 游客态自测 ==")
    c2 = CollectsClient(guest=True)
    print("游客 cookie 字段:", [k.split("=")[0] for k in c2.cookie.split("; ")])
    v = c2.visibility("MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw")
    print("小满收藏公开性:", v)
