# -*- coding: utf-8 -*-
import json, os, sqlite3
base = r"F:\D\Android-Hook"
assets = []
for name in ["privacy_matrix_v4.json","collects_visibility_scan.json","others_collects_full.json",
             "real_likes_web.json","comments_top50.json","videos_top50.json","real_following_app.json",
             "real_favorites.json","ten_users_likes.json","download_manifest.json","app_requests.json"]:
    p = os.path.join(base, "输出数据", name)
    if os.path.exists(p):
        try:
            data = json.load(open(p, encoding="utf-8"))
            n = len(data) if isinstance(data, (list, dict)) else "?"
            assets.append({"name": name, "records": n, "kb": round(os.path.getsize(p)/1024, 1)})
        except Exception as e:
            assets.append({"name": name, "err": str(e)[:50]})
# videos
vd = os.path.join(base, "视频下载")
if os.path.isdir(vd):
    mp4s = [f for f in os.listdir(vd) if f.lower().endswith(".mp4")]
    total = sum(os.path.getsize(os.path.join(vd, f)) for f in mp4s)
    assets.append({"name": "视频下载/*.mp4", "records": len(mp4s), "mb": round(total/1048576, 1)})
# cache db
cdb = os.path.join(base, "输出数据", "huoxiao_cache.db")
if os.path.exists(cdb):
    conn = sqlite3.connect(cdb)
    tabs = {}
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        try: tabs[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except: tabs[t] = -1
    conn.close()
    assets.append({"name": "huoxiao_cache.db", "records": tabs, "mb": round(os.path.getsize(cdb)/1048576, 2)})
# 服务目录
sv = os.path.join(base, "服务")
svfiles = sorted(f for f in os.listdir(sv) if f.endswith(".py") or f.endswith(".md") or f.endswith(".bat"))
print(json.dumps({"assets": assets, "service_files": svfiles}, ensure_ascii=False, indent=1))
