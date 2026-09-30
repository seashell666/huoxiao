# -*- coding: utf-8 -*-
"""火枭 Web 端通道：vault 网页 Cookie + a_bogus 签名（绕开 App 端 bd-ticket-guard 动态签名锁）
已验证（2026-09-26）：
  - get_user_favorite  收藏列表：翻页稳定，55-67 条/节点 ✅
  - get_user_like_list 喜欢列表：2-19 条（Web 端展示限制），真实数据 ✅
用法：WebChannel().get_likes(sec) / get_collects(sec) / visibility(sec)
"""
import os
import sys
import time

sys.path.insert(0, r"F:\D\20-火枭\参考-DouYin_Spider")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"

VAULT = r"C:\Users\Administrator\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\douyin-cookie-vault\assets\douyin_cookie.txt"


def _load_auth():
    from builder.auth import DouyinAuth
    with open(VAULT, encoding="utf-8") as f:
        ck = f.read().strip()
    return DouyinAuth.from_cookie(ck)


class WebChannel:
    """Web 端通道（vault cookie + a_bogus），生产主力"""

    def __init__(self, min_interval=1.5, max_collect_pages=2):
        self._auth = None
        self.min_interval = min_interval
        self.max_collect_pages = max_collect_pages
        self._last = 0.0

    @property
    def auth(self):
        if self._auth is None:
            self._auth = _load_auth()
        return self._auth

    def _throttle(self):
        gap = time.time() - self._last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self._last = time.time()

    @staticmethod
    def _norm_item(it):
        """统一字段：封面/点赞/视频入口/作者，与 App 通道 _norm 对齐"""
        author = it.get("author") or {}
        stats = it.get("statistics") or {}
        vid = it.get("aweme_id") or ""
        share = it.get("share_url") or ""
        if not share and vid:
            share = f"https://www.iesdouyin.com/share/video/{vid}"
        cover = ""
        cov = it.get("video") or {}
        if cov.get("cover"):
            ul = cov["cover"].get("url_list") or []
            cover = ul[0] if ul else ""
        avatar = ""
        av = author.get("avatar_thumb") or {}
        al = av.get("url_list") or []
        avatar = al[0] if al else ""
        return {
            "aweme_id": vid,
            "desc": str(it.get("desc") or "")[:60],
            "cover": cover,
            "digg": stats.get("digg_count") or 0,
            "share_url": share,
            "author": {"nickname": author.get("nickname") or "", "avatar": avatar},
        }

    def get_likes(self, sec, count=20):
        """Web 端喜欢列表（post + tab=like），单页为主（Web 端有限展示）"""
        self._throttle()
        from dy_apis.douyin_api import DouyinAPI
        try:
            j = DouyinAPI.get_user_like_list(self.auth, sec, max_cursor="0", num=str(count))
        except Exception as e:
            return [], False, "0", {"status": 500, "err": f"{type(e).__name__}:{str(e)[:80]}"}
        st = j.get("status_code")
        if st != 0:
            return [], False, "0", {"status": st, "closed": st in (3002279,)}
        lst = j.get("aweme_list") or []
        return [self._norm_item(a) for a in lst], False, "0", {"status": 0}

    def get_collects(self, sec, count=40):
        """Web 端收藏列表（favorite），翻页到 count 条"""
        items = []
        cursor = "0"
        for _ in range(self.max_collect_pages + 1):
            self._throttle()
            from dy_apis.douyin_api import DouyinAPI
            try:
                j = DouyinAPI.get_user_favorite(self.auth, sec, max_cursor=cursor, num="20")
            except Exception as e:
                return items, False, "0", {"status": 500, "err": f"{type(e).__name__}:{str(e)[:80]}"}
            st = j.get("status_code")
            if st != 0:
                return items, False, "0", {"status": st, "closed": st in (3002279,)}
            lst = j.get("aweme_list") or []
            items.extend(lst)
            if not j.get("has_more") or not lst or len(items) >= count:
                break
            cursor = str(j.get("max_cursor") or "0")
        return [self._norm_item(a) for a in items[:count]], False, "0", {"status": 0}

    def visibility(self, sec):
        """可见性判定：收藏/喜欢任一接口 status=0 且有条目 => 公开"""
        self._throttle()
        from dy_apis.douyin_api import DouyinAPI
        try:
            j = DouyinAPI.get_user_favorite(self.auth, sec, max_cursor="0", num="1")
        except Exception as e:
            return {"status": 500, "err": str(e)[:80]}
        st = j.get("status_code")
        n = len(j.get("aweme_list") or [])
        return {"status": st, "open": st == 0 and n > 0, "n": n}


if __name__ == "__main__":
    w = WebChannel()
    sec = "MS4wLjABAAAAWMDSHY8f0C6DdNGkj7XJJvAda4BhoL4bfMOYrtVr2gw"
    print("== Web 喜欢 ==")
    items, more, cur, meta = w.get_likes(sec, 20)
    print(f"n={len(items)} meta={meta}")
    if items:
        print("  首条:", items[0]["desc"], "| 赞:", items[0]["digg"], "| 封面:", items[0]["cover"][:60])
    print("== Web 收藏 ==")
    items2, more, cur, meta2 = w.get_collects(sec, 40)
    print(f"n={len(items2)} meta={meta2}")
    if items2:
        print("  首条:", items2[0]["desc"], "| 赞:", items2[0]["digg"])
    print("== visibility ==")
    print(w.visibility(sec))
