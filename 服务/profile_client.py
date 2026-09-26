# -*- coding: utf-8 -*-
"""火枭采集器：App 端用户主页（节点用户详情）
接口：https://aweme.snssdk.com/aweme/v1/user/?sec_user_id=xxx
发现记录：2026-09-26 实测确认，游客 cookie 即可拿公开主页信息
返回字段：nickname/avatar_thumb/signature/follower_count/following_count/
         favoriting_count/total_favorited/gender/region/birthday/user_age
节点设计逻辑：以节点（用户）为单位，先载入用户详情 profile，再进喜欢/收藏等列表
"""
import io, os, sys, time
import requests

UA_OKHTTP = "okhttp/4.9.2"
HOST = "https://aweme.snssdk.com"
API_USER = "/aweme/v1/user/"

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
KLINK = "AAILyRJYFdxlIx2MLtxIbkJ18zx5ICEM6-PYaPYj2tkbVDyFRgUbYLlb"


class ProfileClient:
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

    def _url(self, sec):
        params = {
            "enter_from": "others_homepage", "tpsa_version": "1",
            "address_book_access": "2", "from": "0", "webcast_plugin_ready": "true",
            "card_partition": "0", "card_style": "0", "hit_ab_test": "1", "btn_in_value": "0",
            "use_profile_show_identify_auth_info": "true", "show_freq_visit_card_bubble": "1",
            "publish_video_strategy_type": "2", "sec_user_id": sec,
            "klink_egdi": KLINK, "iid": IID, "device_id": DEVICE_ID,
            "_rticket": str(int(time.time() * 1000)), "ts": str(int(time.time())), "cdid": CDID,
        }
        params.update(DEVICE_PARAMS)
        q = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{HOST}{API_USER}?{q}"

    def get_profile(self, sec):
        """拿节点用户主页详情。返回 (profile_dict, meta)
        meta: {"status": int}
        """
        url = self._url(sec)
        hdrs = {"User-Agent": UA_OKHTTP, "Cookie": self.cookie}
        r = self._s.get(url, headers=hdrs, timeout=20, verify=False)
        j = r.json()
        st = j.get("status_code")
        if st != 0:
            return None, {"status": st}
        u = j.get("user") or {}
        def _fmt(u):
            """CDN 头像统一转 jpeg（浏览器可显示；heic 直接改扩展名）"""
            if not u:
                return ""
            return u.replace(".heic", ".jpeg")
        profile = {
            "sec_uid": sec,
            "uid": u.get("uid", ""),
            "nickname": u.get("nickname", ""),
            "avatar": _fmt((u.get("avatar_thumb") or {}).get("url_list", [""])[0] or ""),
            "avatar_larger": _fmt((u.get("avatar_larger") or {}).get("url_list", [""])[0] or ""),
            "signature": u.get("signature", ""),
            "follower_count": u.get("follower_count", 0),
            "following_count": u.get("following_count", 0),
            "favoriting_count": u.get("favoriting_count", 0),
            "total_favorited": u.get("total_favorited", 0),
            "gender": u.get("gender", 0),
            "region": u.get("region", ""),
            "birthday": u.get("birthday", ""),
            "user_age": u.get("user_age", 0),
        }
        return profile, {"status": 0}


if __name__ == "__main__":
    import json
    pc = ProfileClient(guest=True)
    for sec in sys.argv[1:] or ["MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"]:
        p, m = pc.get_profile(sec)
        print(json.dumps(p, ensure_ascii=False, indent=2) if p else f"status={m}")
