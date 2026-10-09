# -*- coding: utf-8 -*-
"""火枭统一采集客户端（v2：游客通道 + 登录通道分离）

已验证能力矩阵（2026-09-19 实测）：
  ┌────────────────┬───────────────┬──────────────┐
  │ 接口            │ 游客通道        │ 登录通道(webSign)│
  ├────────────────┼───────────────┼──────────────┤
  │ collects 收藏    │ ✅ App 直连    │ ✅            │
  │ detail 视频详情  │ ✅ App 直连    │ ✅            │
  │ visibility 收藏维│ ✅ App 判定    │ ✅ 全维度       │
  │ likes 喜欢       │ ❌ 空壳        │ ✅            │
  │ comments 评论    │ ❌ 空壳        │ ✅            │
  │ posts 作品       │ ❌ 空壳        │ ✅            │
  │ following/follower│ ❌ status=8  │ ✅            │
  └────────────────┴───────────────┴──────────────┘
设计：游客通道生产主力（零封号）；登录通道用 vault 隔离身份（主号仅开发验真/备用号生产）
"""
import os
import random
import sys
import time

sys.path.insert(0, r"F:\D\20-火枭\参考-DouYin_Spider")
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"

import requests

from builder.auth import DouyinAuth
from builder.header import HeaderBuilder, HeaderType
from builder.params import Params
from utils.secsdk_web_sign import sign_url

from collects_client import CollectsClient
from likes_client import LikesClient
from profile_client import ProfileClient

WEB = "https://www.douyin.com"
REF_USER = lambda sec: f"{WEB}/user/{sec}"
REF_VIDEO = lambda aid: f"{WEB}/video/{aid}"


class GuestChannel:
    """游客通道：collects/detail/visibility(收藏维) —— App 端直连，零签名零登录"""

    def __init__(self, min_interval=1.5):
        self.app = CollectsClient(guest=True)
        self.likes_app = LikesClient(guest=True)
        self.profile_app = ProfileClient(guest=True)
        self.min_interval = min_interval
        self._last = 0.0
        self._fail = {}

    def _throttle(self):
        gap = time.time() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.time()

    def _guard(self, key):
        """2096 指数退避：冷却期内拒绝"""
        import cache
        wait = cache.cooldown_wait(key)
        if wait > 0:
            raise RuntimeError(f"cooldown:{wait}s")
        self._throttle()

    def _mark_fail(self, key, code):
        import cache
        n = self._fail.get(key, 0) + 1
        self._fail[key] = n
        if code in (2096, 8, 3002279) or code >= 400:
            cache.cooldown_set(key, 5.0, n)
        elif code == 0:
            self._fail[key] = 0

    def get_collects(self, sec, count=20):
        self._guard(f"guest:collects:{sec}")
        items, meta = self.app.fetch_all(sec, max_pages=1, sleep_range=None)
        if meta.get("closed"):
            return [], False, "0", {"status": 3002279, "closed": True}
        import cache
        items = cache.interference_filter(items)
        return [HuoxiaoClient._norm(a) for a in items], False, "0", {"status": 0}

    def get_likes(self, sec, count=20, max_pages=2, sleep_range=(1.2, 2.5)):
        """游客通道拿喜欢列表（App端接口）
        max_pages=2 → 翻2页约40条（与面板 A/F 翻页 5 页匹配）
        """
        self._guard(f"guest:likes:{sec}")
        items, meta = self.likes_app.fetch_all(sec, max_pages=max_pages, sleep_range=sleep_range)
        if meta.get("closed"):
            return [], False, "0", {"status": 3002279, "closed": True}
        import cache
        items = cache.interference_filter(items)
        return [HuoxiaoClient._norm(a) for a in items], False, "0", {"status": 0}

    def get_profile(self, sec):
        """节点用户详情（节点=用户，先载入用户信息再进列表）"""
        self._guard(f"guest:profile:{sec}")
        prof, meta = self.profile_app.get_profile(sec)
        if meta.get("status") != 0:
            self._mark_fail(f"guest:profile:{sec}", meta.get("status", 500))
        return prof, meta

    def get_detail(self, aid):
        self._guard(f"guest:detail:{aid}")
        j = self.app.get_page_detail(aid) if hasattr(self.app, "get_page_detail") else None
        if j is None:
            return None, {"status": 501, "err": "guest detail unavailable"}
        st = j.get("status_code")
        d = j.get("aweme_detail") or {}
        if st != 0:
            self._mark_fail(f"guest:detail:{aid}", st)
            return None, {"status": st}
        return HuoxiaoClient._norm(d, detail=True), {"status": 0}

    def get_detail_raw(self, aid):
        """带限流的原始 detail（补采字段用）：返回未归一化的 aweme_detail"""
        self._guard(f"guest:detail:{aid}")
        j = self.app.get_page_detail(aid) if hasattr(self.app, "get_page_detail") else None
        if j is None:
            return None, {"status": 501, "err": "guest detail unavailable"}
        st = j.get("status_code")
        d = j.get("aweme_detail") or {}
        if st != 0:
            self._mark_fail(f"guest:detail:{aid}", st)
            return None, {"status": st}
        return d, {"status": 0}

    def visibility(self, sec):
        """游客通道可见性判定：同时判断收藏+喜欢两个列表"""
        out = {}
        # 收藏
        try:
            self._guard(f"guest:vis:collects:{sec}")
            v = self.app.visibility(sec)
            out["collects"] = "open" if v.get("open") else ("closed" if v.get("closed") else "risk")
        except Exception as e:
            out["collects"] = f"err:{type(e).__name__}"
        # 喜欢
        try:
            self._guard(f"guest:vis:likes:{sec}")
            v = self.likes_app.visibility(sec)
            out["likes"] = "open" if v.get("open") else ("closed" if v.get("closed") else "risk")
        except Exception as e:
            out["likes"] = f"err:{type(e).__name__}"
        # 判定是不是私密账号（两个都closed大概率是私密）
        out["is_private"] = out.get("collects", "") == "closed" and out.get("likes", "") == "closed"
        return out


class AuthChannel:
    """登录通道：likes/comments/posts/following/follower/visibility全维度 —— Web webSign 签名"""

    def __init__(self, cookie_str, min_interval=5.0):
        self.auth = DouyinAuth.from_cookie(cookie_str)
        self.min_interval = min_interval
        self._last = 0.0
        self._fail = {}

    def _throttle(self):
        gap = time.time() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.time()

    def _guard(self, key):
        """冷却 + 主号日预算 + 滑动 2h 预算（config.MAIN_DAILY_BUDGET / MAIN_2H_BUDGET）"""
        import cache
        import config
        if cache.main_budget_used() >= config.MAIN_DAILY_BUDGET:
            raise RuntimeError("main_budget_exhausted")
        if cache.main_2h_budget_used() >= config.MAIN_2H_BUDGET:
            raise RuntimeError("main_2h_budget_exhausted")
        wait = cache.cooldown_wait(f"auth:{key}")
        if wait > 0:
            raise RuntimeError(f"cooldown:{wait}s")
        self._throttle()

    def _mark(self, key, code):
        import cache
        n = self._fail.get(key, 0) + 1
        if code == 0:
            self._fail[key] = 0
            return
        self._fail[key] = n
        if code in (2096, 8) or code >= 400:
            cache.cooldown_set(f"auth:{key}", 5.0, n)

    def web_get(self, api, params, refer):
        import cache
        cache.main_budget_tick()  # 登录通道请求计入主号预算
        self._guard(api.split("/")[-1] + ":" + str(params.get("sec_user_id", params.get("aweme_id", ""))))
        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(refer)
        headers.with_uifid(self.auth)
        p = Params()
        for k, v in params.items():
            p.add_param(k, v)
        p.add_param("device_platform", "webapp")
        p.add_param("aid", "6383")
        p.add_param("channel", "channel_pc_web")
        p.with_platform(round_trip_time=str(random.randint(0, 60)))
        p.with_web_id(auth=self.auth, url=refer)
        p.with_uifid(self.auth)
        p.with_verify_fp(self.auth)
        p.add_param("msToken", self.auth.msToken)
        p.with_a_bogus()
        raw = p.signed_url(f"{WEB}{api}", self.auth)
        uifid = None
        for q in raw.split("?", 1)[1].split("&"):
            if q.startswith("uifid="):
                uifid = q.split("=", 1)[1]
                break
        signed = sign_url(raw, uifid=uifid)
        r = requests.get(signed, headers=headers.get(), cookies=self.auth.cookie, timeout=20, verify=False)
        j = r.json()
        self._mark(api.split("/")[-1], j.get("status_code", 0))
        return j

    def get_likes(self, sec, cursor=0, count=20):
        j = self.web_get("/aweme/v1/web/aweme/favorite/",
                         {"sec_user_id": sec, "max_cursor": cursor, "count": count},
                         REF_USER(sec))
        st = j.get("status_code")
        if st != 0:
            return [], False, cursor, {"status": st}
        import cache
        items = cache.interference_filter(j.get("aweme_list") or [])
        return ([HuoxiaoClient._norm(a) for a in items],
                bool(j.get("has_more")), j.get("max_cursor", cursor), {"status": 0})

    def get_comments(self, aid, cursor=0, count=20):
        j = self.web_get("/aweme/v1/web/comment/list/",
                         {"aweme_id": aid, "cursor": cursor, "count": count},
                         REF_VIDEO(aid))
        st = j.get("status_code")
        if st != 0:
            return [], False, cursor, {"status": st}
        items = []
        for c in (j.get("comments") or []):
            u = c.get("user") or {}
            av = (u.get("avatar_thumb") or {}).get("url_list") or [""]
            # 数据采集规范：一次请求全字段落库，禁止裁剪。raw 保留完整原始评论 JSON。
            items.append({
                "comment_id": c.get("cid", ""),
                "text": c.get("text", ""),
                "digg_count": c.get("digg_count", 0),
                "reply_count": c.get("reply_comment_total", 0),
                "create_time": c.get("create_time", 0),
                "ip_label": c.get("ip_label", "") or "",
                "user": {"nickname": u.get("nickname", ""), "sec_uid": u.get("sec_uid", ""),
                         "avatar": av[0] if av else ""},
                "reply_comment": c.get("reply_comment") or None,
                "raw": c,
            })
        return items, bool(j.get("has_more")), j.get("cursor", cursor), {"status": 0}

    def get_posts(self, sec, cursor=0, count=20):
        j = self.web_get("/aweme/v1/web/aweme/post/",
                         {"sec_user_id": sec, "max_cursor": cursor, "count": count},
                         REF_USER(sec))
        st = j.get("status_code")
        if st != 0:
            return [], False, cursor, {"status": st}
        import cache
        items = cache.interference_filter(j.get("aweme_list") or [])
        return ([HuoxiaoClient._norm(a) for a in items],
                bool(j.get("has_more")), j.get("max_cursor", cursor), {"status": 0})

    def get_following(self, sec, cursor=0, count=20):
        return self._user_list("/aweme/v1/web/user/following/list/", sec, cursor, count, "followings")

    def get_follower(self, sec, cursor=0, count=20):
        return self._user_list("/aweme/v1/web/user/follower/list/", sec, cursor, count, "followers")

    def _user_list(self, api, sec, cursor, count, key):
        j = self.web_get(api, {"sec_user_id": sec, "max_cursor": cursor, "count": count, "source_type": 0},
                         REF_USER(sec))
        st = j.get("status_code")
        if st != 0:
            return [], False, cursor, {"status": st}
        return ([{"sec_uid": u.get("sec_uid", ""), "nickname": u.get("nickname", ""),
                  "unique_id": u.get("unique_id", "")} for u in (j.get(key) or [])],
                bool(j.get("has_more")), j.get("max_cursor", cursor), {"status": 0})

    def get_visibility_full(self, sec):
        """全维度公开性（登录通道）"""
        out = {}
        for key, api, extra in (
                ("favorite", "/aweme/v1/web/aweme/favorite/", {"sec_user_id": sec, "max_cursor": 0, "count": 5}),
                ("following", "/aweme/v1/web/user/following/list/", {"sec_user_id": sec, "max_cursor": 0, "count": 5, "source_type": 0}),
                ("follower", "/aweme/v1/web/user/follower/list/", {"sec_user_id": sec, "max_cursor": 0, "count": 5, "source_type": 0})):
            try:
                j = self.web_get(api, extra, REF_USER(sec))
                st = j.get("status_code")
                lst = j.get("aweme_list") or j.get("user_list") or j.get("followings") or j.get("followers") or []
                out[key] = "open" if st == 0 and len(lst) > 0 else ("closed" if st == 3002279 else f"risk:{st}")
            except Exception as e:
                out[key] = f"err:{type(e).__name__}"
        return out

    def get_detail_raw(self, aid):
        """作品详情（登录通道）：guest 拿不到的私密/风控内容走主号"""
        j = self.web_get("/aweme/v1/web/aweme/detail/", {"aweme_id": aid}, REF_VIDEO(aid))
        st = j.get("status_code", 0)
        d = j.get("aweme_detail") or {}
        return d, {"status": st}


class HuoxiaoClient:
    """统一入口：游客通道 + 可选登录通道"""

    def __init__(self, cookie_str=None, guest_interval=1.5, auth_interval=5.0):
        self.guest = GuestChannel(guest_interval)
        self.auth = AuthChannel(cookie_str, auth_interval) if cookie_str else None

    @staticmethod
    def _pick_url(obj, prefer_jpeg=True):
        """从 url_list 挑无水印 jpeg 档，失败回退第一个"""
        if isinstance(obj, dict):
            ul = obj.get("url_list") or []
            if prefer_jpeg:
                for u in ul:
                    if ".jpeg" in u and "aweme-images" in u:
                        return u
            return ul[0] if ul else ""
        return obj or ""

    @staticmethod
    def _norm(a, detail=False):
        st = a.get("statistics") or {}
        au = a.get("author") or {}
        vid = a.get("video") or {}
        base = {
            "aweme_id": a.get("aweme_id", ""),
            "desc": a.get("desc", ""),
            "create_time": a.get("create_time", 0),
            "author": {"nickname": au.get("nickname", ""), "sec_uid": au.get("sec_uid", ""), "uid": au.get("uid", ""),
               "avatar": (au.get("avatar_thumb") or {}).get("url_list", [""])[0] if au.get("avatar_thumb") else ""},
            "stats": {"digg": st.get("digg_count", 0), "comment": st.get("comment_count", 0),
                      "collect": st.get("collect_count", 0), "share": st.get("share_count", 0)},
            "duration": a.get("duration", 0),
            "cover": (vid.get("cover") or {}).get("url_list", [""])[0] if vid.get("cover") else "",
        }
        if detail:
            br = vid.get("bit_rate") or []
            gear = next((str(b.get("gear_name") or "") for b in br if "1080" in str(b.get("gear_name") or "")), None)
            src = None
            if gear:
                src = (next(b for b in br if "1080" in str(b.get("gear_name") or "")).get("play_addr") or {}).get("url_list") or [None]
                src = src[0]
            if not src:
                src = (vid.get("download_addr") or {}).get("url_list") or (vid.get("play_addr") or {}).get("url_list") or [None]
                src = src[0] if src else None
            mu = a.get("music") or {}
            imgs = a.get("images") or []
            base.update({"width": vid.get("width", 0), "height": vid.get("height", 0),
                         "quality": gear or "play_addr", "play_url": src,
                         "music": {"id": mu.get("id", ""), "title": mu.get("title", ""),
                                   "author": mu.get("author", ""),
                                   "cover": HuoxiaoClient._pick_url(mu.get("cover_medium")),
                                   "cover_large": HuoxiaoClient._pick_url(mu.get("cover_large")),
                                   "cover_hd": HuoxiaoClient._pick_url(mu.get("cover_hd")),
                                   "play_url": HuoxiaoClient._pick_url(mu.get("play_url"), prefer_jpeg=False)},
                         "author_avatar_thumb": HuoxiaoClient._pick_url(au.get("avatar_thumb")),
                         "author_avatar_medium": HuoxiaoClient._pick_url(au.get("avatar_medium")),
                         "is_imagepost": bool(imgs),
                         "images": [HuoxiaoClient._pick_url(i) for i in imgs if isinstance(i, dict) and i.get("url_list")],
                         "music_cover_all": [HuoxiaoClient._pick_url(mu.get(k), prefer_jpeg=False) for k in ("cover_thumb", "cover_medium", "cover_large", "cover_hd") if mu.get(k)]})
        return base


def load_vault_cookie():
    """读取 vault 登录态 cookie"""
    p = r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\douyin-cookie-vault\assets\douyin_cookie.txt"
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    return None


def vault_status():
    """vault cookie 有效性检测（主号隔离：仅开发验真，绝不进生产链路）"""
    ck = load_vault_cookie()
    if not ck:
        return {"present": False, "valid": False, "msg": "vault 无 cookie"}
    try:
        a = DouyinAuth.from_cookie(ck)
        uid = a.get_uid()
        has_ssid = "sessionid" in ck
        return {"present": True, "valid": has_ssid and bool(uid),
                "uid": uid, "has_sessionid": has_ssid, "msg": "ok"}
    except Exception as e:
        return {"present": True, "valid": False, "msg": f"{type(e).__name__}:{str(e)[:100]}"}


if __name__ == "__main__":
    print("== 自测 ==")
    c = HuoxiaoClient()
    sec = "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"  # 小满
    print("游客 visibility_collects:", c.guest.visibility_collects(sec))
    time.sleep(2)
    items, more, cur, meta = c.guest.get_collects(sec)
    print(f"游客 collects: n={len(items)} meta={meta} 首条={str(items[0].get('desc'))[:25] if items else ''}")
