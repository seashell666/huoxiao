# -*- coding: utf-8 -*-
"""火枭采集服务入口（P1 骨架）
运行：venv\Scripts\python.exe server.py
"""
import os
import time

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import cache
import config
import huoxiao_client as hx
import downloads

app = FastAPI(title="火枭采集服务", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(downloads.router)

# 启动初始化
cache.init()
_guest = hx.GuestChannel()          # 游客通道单例（生产主力）
_auth = None                        # 登录通道懒加载（仅开发验真）


def _get_auth():
    """懒加载登录通道（vault cookie，主号=开发验真专用）"""
    global _auth
    if _auth is None:
        ck = hx.load_vault_cookie()
        if ck:
            _auth = hx.AuthChannel(ck)
    return _auth

PANEL_HTML = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>火枭 · 运营面板</title>
<style>
:root{--bg:#FDF6EF;--card:#fff;--ink:#2A1A12;--sub:#8A6F5E;--line:#F0E2D4;--fire:#FF6B35;--green:#35705A;--red:#A14E50;--amber:#9A6A2F}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:20px}
h1{font-size:22px;margin-bottom:4px}.sub{color:var(--sub);font-size:12px;margin-bottom:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.card b{display:block;font-size:22px;color:var(--fire)}.card span{font-size:11px;color:var(--sub)}
h2{font-size:16px;margin:18px 0 8px;border-left:4px solid var(--fire);padding-left:8px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;table-layout:fixed}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid #FAF1E8;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
th{background:#FFF7F0;color:var(--sub);font-weight:600}
.ok{color:var(--green)}.bad{color:var(--red)}.warn{color:var(--amber)}
.seg{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.seg button{border:1px solid var(--line);background:#fff;border-radius:20px;padding:5px 14px;cursor:pointer;font-size:12px}
.seg button.on{background:var(--fire);color:#fff;border-color:var(--fire)}
</style></head><body>
<h1>火枭 · 运营面板</h1>
<div class="sub" id="date"></div>
<div class="cards" id="ov"></div>
<div class="seg" id="seg">
<button class="on" onclick="setDays(7)">近7天</button><button onclick="setDays(3)">近3天</button><button onclick="setDays(1)">昨天</button><button onclick="setDays(0)">今天</button>
</div>
<div id="days"></div>
<h2>节点状态</h2>
<div id="nodes"></div>
<h2>失败清单（要了没给成功的）</h2>
<div id="fails"></div>
<h2>反复调用热榜</h2>
<div id="hot"></div>
<script>
const A='__KEY__';
async function j(u){const r=await fetch(u,{headers:{'X-Api-Key':A}});return r.json()}
function esc(s){return String(s==null?'':s).replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]))}
async function load(){
  const ov=await j('/v1/panel/overview');
  document.getElementById('date').textContent='统计日期 '+ov.date;
  document.getElementById('ov').innerHTML=
    card('今日请求',ov.req_total)+card('成功',ov.req_ok)+card('失败',ov.req_fail)+
    card('缓存命中率',(ov.cache_hit_rate*100).toFixed(1)+'%')+card('1h风控',ov.cooling_1h)+
    card('活跃节点',ov.nodes_active)+card('缓存库',ov.cache_db_mb+'MB')+
    card('主号预算',(ov.main_budget_used||0)+'/'+ov.main_budget_limit);
  const days=await j('/v1/panel/days?days='+DAYS);
  document.getElementById('days').innerHTML='<table><colgroup><col style="width:20%"><col style="width:16%"><col style="width:16%"><col style="width:16%"><col style="width:16%"><col style="width:16%"></colgroup><tr><th>日期</th><th>请求</th><th>成功</th><th>失败</th><th>缓存命中</th><th>命中率</th></tr>'+
    days.map(d=>'<tr><td>'+d.date+'</td><td>'+d.req_total+'</td><td class="ok">'+d.req_ok+'</td><td class="bad">'+d.req_fail+'</td><td>'+d.req_cached+'</td><td>'+(d.cache_hit_rate*100).toFixed(1)+'%</td></tr>').join('')+'</table>';
  const ns=await j('/v1/panel/nodes');
  document.getElementById('nodes').innerHTML=ns.length?'<table><colgroup><col style="width:30%"><col style="width:14%"><col style="width:12%"><col style="width:24%"><col style="width:20%"></colgroup><tr><th>用户</th><th>状态</th><th>visibility</th><th>进度</th><th>更新</th></tr>'+
    ns.map(n=>{const p=n.progress||{};return '<tr><td>'+esc(n.nickname||n.sec_uid.slice(0,12))+'</td><td>'+statusTag(n.status)+'</td><td>'+visTag(p.visibility)+'</td><td>喜欢 '+fmt(p.likes)+' 收藏 '+fmt(p.collects)+' 作品 '+fmt(p.posts)+'</td><td>'+fmtTime(n.updated_at)+'</td></tr>'}).join('')+'</table>':'<div class="sub">暂无节点</div>';
  const fl=await j('/v1/panel/failures?limit=30');
  document.getElementById('fails').innerHTML=fl.length?'<table><colgroup><col style="width:24%"><col style="width:30%"><col style="width:26%"><col style="width:20%"></colgroup><tr><th>时间</th><th>接口</th><th>目标</th><th>错误码</th></tr>'+
    fl.map(f=>'<tr><td>'+fmtTime(f.ts)+'</td><td>'+esc(f.endpoint)+'</td><td>'+esc(f.target)+'</td><td class="bad">'+f.code+'</td></tr>').join('')+'</table>':'<div class="sub">无失败</div>';
  const hk=await j('/v1/panel/hotkeys');
  document.getElementById('hot').innerHTML=hk.length?'<table><colgroup><col style="width:44%"><col style="width:18%"><col style="width:18%"><col style="width:20%"></colgroup><tr><th>目标</th><th>请求次数</th><th>已缓存</th><th>未缓存</th></tr>'+
    hk.map(h=>'<tr><td>'+esc(h.target)+'</td><td>'+h.times+'</td><td class="ok">'+h.cached+'</td><td class="warn">'+h.uncached+'</td></tr>').join('')+'</table>':'<div class="sub">暂无数据</div>';
}
function card(t,v){return '<div class="card"><b>'+v+'</b><span>'+t+'</span></div>'}
function statusTag(s){const m={pending:'待采',collecting:'采集中',done:'完成',failed:'失败',private:'私密',cached:'缓存命中'};return '<span class="'+(s==='done'||s==='cached'?'ok':s==='failed'||s==='private'?'bad':'warn')+'">'+esc(m[s]||s)+'</span>'}
function visTag(v){return v===1?'<span class="ok">✓</span>':v===0?'<span class="bad">✗</span>':'—'}
function fmt(p){if(!p)return '—';const a=String(p).split('/');return a.length===2?a[0]+'/'+a[1]:p}
function fmtTime(t){if(!t)return '—';const d=new Date(t*1000);return d.getMonth()+1+'/'+d.getDate()+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}
let DAYS=7;function setDays(n){DAYS=n;document.querySelectorAll('#seg button').forEach(b=>b.classList.remove('on'));event.target.classList.add('on');load()}
load();setInterval(load,15000);
</script></body></html>"""


def _check_key(x_api_key: str):
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


# ---------- 基础 ----------

@app.get("/health")
def health():
    return {"code": 0, "data": {"status": "ok", "ts": int(time.time()), "queue": 0}}


@app.get("/v1/health")
def health_v1(x_api_key: str = Header("")):
    _check_key(x_api_key)
    return health()


@app.get("/v1/vault/status")
def vault_status_api(x_api_key: str = Header("")):
    """主号隔离：vault cookie 有效性检测（仅开发验真）"""
    _check_key(x_api_key)
    st = hx.vault_status()
    st["main_budget_used"] = cache.main_budget_used()
    st["main_budget_limit"] = config.MAIN_DAILY_BUDGET
    return {"code": 0, "data": st, "meta": {}}


# ---------- 运营面板 ----------

@app.get("/panel", response_class=HTMLResponse)
def panel_page():
    return PANEL_HTML.replace("__KEY__", config.API_KEY)


@app.get("/v1/panel/overview")
def panel_overview(x_api_key: str = Header("")):
    _check_key(x_api_key)
    ov = cache.panel_overview()
    ov["main_budget_used"] = cache.main_budget_used()
    ov["main_budget_limit"] = config.MAIN_DAILY_BUDGET
    return {"code": 0, "data": ov}


@app.get("/v1/panel/days")
def panel_days(days: int = 7, x_api_key: str = Header("")):
    _check_key(x_api_key)
    return {"code": 0, "data": cache.panel_days(days)}


@app.get("/v1/panel/nodes")
def panel_nodes(x_api_key: str = Header("")):
    _check_key(x_api_key)
    return {"code": 0, "data": cache.node_list()}


@app.get("/v1/panel/failures")
def panel_failures(limit: int = 100, x_api_key: str = Header("")):
    _check_key(x_api_key)
    return {"code": 0, "data": cache.panel_failures(limit)}


@app.get("/v1/panel/hotkeys")
def panel_hotkeys(limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    return {"code": 0, "data": cache.panel_hotkeys(limit)}


# ---------- 采集接口（游客通道优先 / 登录通道兜底） ----------

@app.get("/v1/user/{sec_uid}/visibility")
def api_visibility(sec_uid: str, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    hit = cache.node_cache_get(sec_uid, "visibility")
    if hit:
        cache.log_req("/v1/user/visibility", sec_uid, 0, cached=True, ms=int((time.time() - t0) * 1000))
        return {"code": 0, "data": hit, "meta": {"cached": True}}
    try:
        vis = _guest.visibility_collects(sec_uid)
        code = 0
    except Exception as e:
        cache.log_req("/v1/user/visibility", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.node_cache_set(sec_uid, "visibility", vis)
    cache.node_update(sec_uid, status="pending", progress={"visibility": 1})
    cache.log_req("/v1/user/visibility", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": vis, "meta": {"cached": False}}


@app.get("/v1/user/{sec_uid}/profile")
def api_profile(sec_uid: str, x_api_key: str = Header("")):
    """节点用户主页详情（节点=用户：先载入用户信息再进列表）"""
    _check_key(x_api_key)
    t0 = time.time()
    hit = cache.node_cache_get(sec_uid, "profile")
    if hit:
        cache.log_req("/v1/user/profile", sec_uid, 0, cached=True, ms=int((time.time() - t0) * 1000))
        return {"code": 0, "data": hit, "meta": {"cached": True}}
    try:
        prof, meta = _guest.get_profile(sec_uid)
        code = 0 if meta.get("status") == 0 else meta.get("status", 500)
    except Exception as e:
        cache.log_req("/v1/user/profile", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    if code == 0 and prof:
        cache.node_cache_set(sec_uid, "profile", prof, ttl=config.TTL_A)
        cache.node_update(sec_uid, nickname=prof.get("nickname", ""), status="done", progress={"profile": "ok"})
    cache.log_req("/v1/user/profile", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": prof, "meta": {"cached": False}}


@app.get("/v1/user/{sec_uid}/likes")
def api_likes(sec_uid: str, cursor: int = 0, limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    # 首屏优先走缓存（游客通道已存的 likes 全量）
    if cursor == 0:
        hit = cache.node_cache_get(sec_uid, "likes")
        if hit:
            cache.log_req("/v1/user/likes", sec_uid, 0, cached=True, ms=int((time.time() - t0) * 1000))
            return {"code": 0, "data": {"items": hit, "has_more": False, "cursor": "done"}, "meta": {"cached": True}}
    auth = _get_auth()
    if auth is None:
        cache.log_req("/v1/user/likes", sec_uid, 401, ms=int((time.time() - t0) * 1000))
        return {"code": 401, "data": None, "meta": {"msg": "登录通道未配置（likes 需要登录身份）"}}
    try:
        items, more, cur, meta = auth.get_likes(sec_uid, cursor, limit)
        code = 0 if meta.get("status") == 0 else meta.get("status", 500)
    except Exception as e:
        cache.log_req("/v1/user/likes", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    if code == 0:
        cache.node_update(sec_uid, progress={"likes": f"{len(items)}/{limit}"})
        if cursor == 0:
            cache.node_cache_set(sec_uid, "likes", items, ttl=config.TTL_A)
    cache.log_req("/v1/user/likes", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": {"items": items, "has_more": more, "cursor": cur}, "meta": {"cached": False}}


@app.get("/v1/user/{sec_uid}/collects")
def api_collects(sec_uid: str, cursor: int = 0, limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    hit = cache.node_cache_get(sec_uid, "collects")
    if hit:
        cache.log_req("/v1/user/collects", sec_uid, 0, cached=True, ms=int((time.time() - t0) * 1000))
        return {"code": 0, "data": {"items": hit, "has_more": False, "cursor": "done"}, "meta": {"cached": True}}
    try:
        items, more, cur, meta = _guest.get_collects(sec_uid, limit)
        if meta.get("closed"):
            cache.node_cache_set(sec_uid, "collects", {"closed": True}, ttl=config.TTL_A)
            cache.node_update(sec_uid, status="private", progress={"collects": "closed"})
            cache.log_req("/v1/user/collects", sec_uid, 3002279, cached=False, ms=int((time.time() - t0) * 1000))
            return {"code": 3002279, "data": None, "meta": {"msg": "收藏未公开", "closed": True}}
        code = 0
    except Exception as e:
        cache.log_req("/v1/user/collects", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.node_cache_set(sec_uid, "collects", items)
    cache.node_update(sec_uid, status="done", progress={"collects": f"{len(items)}/all"})
    cache.log_req("/v1/user/collects", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": {"items": items, "has_more": False, "cursor": "done"}, "meta": {"cached": False}}


@app.get("/v1/user/{sec_uid}/posts")
def api_posts(sec_uid: str, cursor: int = 0, limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    auth = _get_auth()
    if auth is None:
        cache.log_req("/v1/user/posts", sec_uid, 401, ms=int((time.time() - t0) * 1000))
        return {"code": 401, "data": None, "meta": {"msg": "登录通道未配置（posts 需要登录身份）"}}
    try:
        items, more, cur, meta = auth.get_posts(sec_uid, cursor, limit)
        code = 0 if meta.get("status") == 0 else meta.get("status", 500)
    except Exception as e:
        cache.log_req("/v1/user/posts", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.log_req("/v1/user/posts", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": {"items": items, "has_more": more, "cursor": cur}, "meta": {"cached": False}}


@app.get("/v1/video/{aweme_id}/detail")
def api_detail(aweme_id: str, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    hit = cache.video_cache_get(aweme_id)
    if hit:
        cache.log_req("/v1/video/detail", aweme_id, 0, cached=True, ms=int((time.time() - t0) * 1000))
        return {"code": 0, "data": hit, "meta": {"cached": True}}
    try:
        d, meta = _guest.get_detail(aweme_id)
        if meta.get("status") != 0 or not d:
            cache.log_req("/v1/video/detail", aweme_id, meta.get("status", 500), ms=int((time.time() - t0) * 1000))
            return {"code": meta.get("status", 500), "data": None, "meta": meta}
        code = 0
    except Exception as e:
        cache.log_req("/v1/video/detail", aweme_id, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.video_cache_set(aweme_id, d)
    cache.log_req("/v1/video/detail", aweme_id, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": d, "meta": {"cached": False}}


@app.get("/v1/video/{aweme_id}/comments")
def api_comments(aweme_id: str, cursor: int = 0, limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    auth = _get_auth()
    if auth is None:
        cache.log_req("/v1/video/comments", aweme_id, 401, ms=int((time.time() - t0) * 1000))
        return {"code": 401, "data": None, "meta": {"msg": "登录通道未配置（comments 需要登录身份）"}}
    try:
        items, more, cur, meta = auth.get_comments(aweme_id, cursor, limit)
        code = 0 if meta.get("status") == 0 else meta.get("status", 500)
    except Exception as e:
        cache.log_req("/v1/video/comments", aweme_id, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.log_req("/v1/video/comments", aweme_id, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": {"items": items, "has_more": more, "cursor": cur}, "meta": {"cached": False}}


@app.get("/v1/user/{sec_uid}/following")
def api_following(sec_uid: str, cursor: int = 0, limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    auth = _get_auth()
    if auth is None:
        cache.log_req("/v1/user/following", sec_uid, 401, ms=int((time.time() - t0) * 1000))
        return {"code": 401, "data": None, "meta": {"msg": "登录通道未配置（following 需要登录身份）"}}
    try:
        items, more, cur, meta = auth.get_following(sec_uid, cursor, limit)
        code = 0 if meta.get("status") == 0 else meta.get("status", 500)
    except Exception as e:
        cache.log_req("/v1/user/following", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.log_req("/v1/user/following", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": {"items": items, "has_more": more, "cursor": cur}, "meta": {"cached": False}}


@app.get("/v1/user/{sec_uid}/follower")
def api_follower(sec_uid: str, cursor: int = 0, limit: int = 20, x_api_key: str = Header("")):
    _check_key(x_api_key)
    t0 = time.time()
    auth = _get_auth()
    if auth is None:
        cache.log_req("/v1/user/follower", sec_uid, 401, ms=int((time.time() - t0) * 1000))
        return {"code": 401, "data": None, "meta": {"msg": "登录通道未配置（follower 需要登录身份）"}}
    try:
        items, more, cur, meta = auth.get_follower(sec_uid, cursor, limit)
        code = 0 if meta.get("status") == 0 else meta.get("status", 500)
    except Exception as e:
        cache.log_req("/v1/user/follower", sec_uid, 500, ms=int((time.time() - t0) * 1000))
        return {"code": 500, "data": None, "meta": {"err": f"{type(e).__name__}:{str(e)[:80]}"}}
    cache.log_req("/v1/user/follower", sec_uid, code, cached=False, ms=int((time.time() - t0) * 1000))
    return {"code": code, "data": {"items": items, "has_more": more, "cursor": cur}, "meta": {"cached": False}}


@app.post("/v1/review/submit")
def review_submit(body: dict, x_api_key: str = Header("")):
    """冷静池人工审核结果落库
    body: {"results": [{"sec_uid": "...", "decision": "pass|block|skip"}]}
    pass  -> 生产池低权重 + 审核通过 + 7天保护期
    block -> 永久拉黑 is_blocked=1
    skip  -> 标记忽略，留在冷静池
    """
    _check_key(x_api_key)
    import sqlite3
    results = body.get("results") or []
    if not results:
        return {"code": 400, "data": None, "meta": {"msg": "results 不能为空"}}
    db = sqlite3.connect(r"F:\D\20-火枭\输出数据\huoxiao_cache.db")
    db.row_factory = sqlite3.Row
    now = int(time.time())
    done = {"pass": 0, "block": 0, "skip": 0}
    errors = []
    for item in results:
        sid = item.get("sec_uid")
        dec = item.get("decision")
        if not sid or dec not in ("pass", "block", "skip"):
            errors.append({"sec_uid": sid, "err": "decision 非法"})
            continue
        if dec == "pass":
            db.execute("UPDATE node_pool SET pool_level='low', audit_status='approved', is_blocked=0, "
                       "score=0.001, protect_until=?, last_updated=? WHERE sec_uid=?", (now + 7 * 86400, now, sid))
        elif dec == "block":
            db.execute("UPDATE node_pool SET is_blocked=1, pool_level='blocked', audit_status='blocked', "
                       "last_updated=? WHERE sec_uid=?", (now, sid))
        else:
            db.execute("UPDATE node_pool SET audit_status='skipped', last_updated=? WHERE sec_uid=?", (now, sid))
        done[dec] += 1
    db.commit()
    db.close()
    cache.log_req("/v1/review/submit", "", 0, cached=False, ms=0)
    return {"code": 0, "data": done, "meta": {"msg": "审核结果已落库", "errors": errors}}


@app.post("/v1/collect_node")
def collect_node(body: dict, x_api_key: str = Header("")):
    """
    以节点为单位批量采集
    body: {
      "sec_uid": "xxx",
      "depth": "deep" | "shallow",  # deep=深度采集，shallow=浅层采集
      "options": {  # 可选，指定采哪些
        "collects": true,
        "likes": true,
        "posts": false,
        "following": false,
        "follower": false,
        "video_detail": false,  # 采不采视频详情
        "comments": false  # 采不采评论
      }
    }
    """
    _check_key(x_api_key)
    sec_uid = body.get("sec_uid")
    depth = body.get("depth", "shallow")
    options = body.get("options", {})

    if not sec_uid:
        return {"code": 400, "data": None, "meta": {"err": "sec_uid is required"}}

    result = {
        "sec_uid": sec_uid,
        "depth": depth,
        "steps": []
    }

    # 第一步：可见性判定
    try:
        vis = _guest.visibility_collects(sec_uid)
        result["steps"].append({"step": "visibility", "ok": True, "data": vis})
        # 如果是私密账号，直接返回
        if vis.get("is_private"):
            result["steps"].append({"step": "stop", "ok": True, "reason": "private account"})
            return {"code": 0, "data": result, "meta": {}}
    except Exception as e:
        result["steps"].append({"step": "visibility", "ok": False, "err": str(e)})
        return {"code": 500, "data": result, "meta": {}}

    # 第二步：收藏列表（默认采，高权重才采）
    if options.get("collects", depth == "deep"):
        try:
            items, more, cur, meta = _guest.get_collects(sec_uid, 20)
            result["steps"].append({"step": "collects", "ok": True, "count": len(items)})
        except Exception as e:
            result["steps"].append({"step": "collects", "ok": False, "err": str(e)})

    # 第三步：喜欢列表（默认都采）
    if options.get("likes", True):
        try:
            auth = _get_auth()
            if auth:
                items, more, cur, meta = auth.get_likes(sec_uid, 0, 20)
                result["steps"].append({"step": "likes", "ok": True, "count": len(items)})

                # 深度采集才进视频详情
                if depth == "deep" and options.get("video_detail", True):
                    # 只采前5个视频的详情，避免太多
                    for i, item in enumerate(items[:5]):
                        aweme_id = item.get("aweme_id")
                        if aweme_id:
                            try:
                                d, meta = _guest.get_detail(aweme_id)
                                result["steps"].append({"step": f"detail_{i}", "ok": True, "aweme_id": aweme_id})
                            except Exception as e:
                                result["steps"].append({"step": f"detail_{i}", "ok": False, "err": str(e)})
            else:
                result["steps"].append({"step": "likes", "ok": False, "err": "auth not configured"})
        except Exception as e:
            result["steps"].append({"step": "likes", "ok": False, "err": str(e)})

    # 第四步：作品列表（散人同好默认不采）
    if options.get("posts", False):
        try:
            auth = _get_auth()
            if auth:
                items, more, cur, meta = auth.get_posts(sec_uid, 0, 20)
                result["steps"].append({"step": "posts", "ok": True, "count": len(items)})
        except Exception as e:
            result["steps"].append({"step": "posts", "ok": False, "err": str(e)})

    return {"code": 0, "data": result, "meta": {}}


if __name__ == "__main__":
    print(f"火枭服务启动 http://{config.HOST}:{config.PORT}  面板 /panel")
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")
