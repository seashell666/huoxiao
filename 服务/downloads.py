# -*- coding: utf-8 -*-
"""P3 下载服务（主号 webSign 低频取链 + 异步下载）
POST /v1/download  {"aweme_ids": [...]}  → {task_id}
GET  /v1/task/{task_id}                  → 任务进度
"""
import json
import os
import random
import sys
import threading
import time
import uuid as _uuid

sys.path.insert(0, r"F:\D\20-火枭\参考-DouYin_Spider")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10809"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:10809"

import requests
from fastapi import APIRouter, Header

import config
import cache
import huoxiao_client as hx

from builder.auth import DouyinAuth
from builder.header import HeaderBuilder, HeaderType as HType
from builder.params import Params
from utils.secsdk_web_sign import sign_url as web_sign_url
from utils import http_client as douyin_http

router = APIRouter()

TASKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")
_tasks = {}
_tasks_lock = threading.RLock()  # 可重入（_save_tasks 在持锁内调用）
_DL_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36")
_DL_HEADERS = {"User-Agent": _DL_UA, "Referer": "https://www.douyin.com/", "Accept": "*/*"}
_auth = None


def _get_auth():
    """懒加载登录态（下载直链需要 DouyinAuth: cookie + webSign）"""
    global _auth
    if _auth is None:
        ck = hx.load_vault_cookie()
        if ck:
            _auth = DouyinAuth.from_cookie(ck)
    return _auth


def _save_tasks():
    with _tasks_lock:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(_tasks, f, ensure_ascii=False, indent=1)


def _load_tasks():
    global _tasks
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, encoding="utf-8") as f:
                _tasks = json.load(f)
        except Exception:
            _tasks = {}


def _fetch_1080p_src(aid, auth):
    """主号 webSign detail → 1080p 直链（无 1080 档则 download_addr 兜底）"""
    headers = HeaderBuilder.build(HType.GET)
    url = f"https://www.douyin.com/video/{aid}"
    headers.set_referer(url)
    headers.with_uifid(auth)
    p = Params()
    for k, v in {"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
                 "aweme_id": aid}.items():
        p.add_param(k, v)
    p.with_platform(round_trip_time="0")
    p.with_web_id(auth=auth, url=url)
    p.with_uifid(auth)
    p.with_verify_fp(auth)
    p.add_param("msToken", auth.msToken)
    p.with_a_bogus()
    raw = p.signed_url("https://www.douyin.com/aweme/v1/web/aweme/detail/", auth)
    uifid = None
    for q in raw.split("?", 1)[1].split("&"):
        if q.startswith("uifid="):
            uifid = q.split("=", 1)[1]
            break
    signed = web_sign_url(raw, uifid=uifid)
    r = douyin_http.get(signed, headers=headers.get(), cookies=auth.cookie, verify=False, timeout=25)
    aw = r.json().get("aweme_detail") or {}
    vid = aw.get("video") or {}
    src, gear = None, None
    for br in vid.get("bit_rate") or []:
        g = str(br.get("gear_name") or "")
        if "1080" in g:
            src = ((br.get("play_addr") or {}).get("url_list") or [None])[0]
            gear = g
            break
    if not src:
        src = ((vid.get("download_addr") or {}).get("url_list") or [None])[0]
        gear = "download_addr"
    if not src:
        src = ((vid.get("play_addr") or {}).get("url_list") or [None])[0]
        gear = "play_addr"
    return src, gear, vid


def _download_worker(task_id):
    with _tasks_lock:
        task = _tasks.get(task_id)
    if not task:
        return
    auth = _get_auth()
    if auth is None:
        task["status"] = "failed"
        task["err"] = "登录通道未配置（下载需要登录身份取 1080p 直链）"
        _save_tasks()
        return
    for i, aid in enumerate(task["aweme_ids"]):
        item = {"aweme_id": aid, "status": "pending"}
        task["items"][str(aid)] = item
        task["status"] = "running"
        task["done_count"] = i
        _save_tasks()
        try:
            src, gear, vid = _fetch_1080p_src(aid, auth)
            if not src:
                item.update({"status": "no_src"})
                task["fail_count"] += 1
                _save_tasks()
                continue
            path = os.path.join(config.VIDEO_DIR, f"{aid}.mp4")
            resp = requests.get(src, headers=_DL_HEADERS, timeout=120, stream=True, verify=False)
            total_bytes = 0
            with open(path, "wb") as f:
                for chunk in resp.iter_content(1 << 16):
                    f.write(chunk)
                    total_bytes += len(chunk)
            ok = total_bytes > 10000
            with open(path, "rb") as f:
                hdr = f.read(12)
            ok = ok and hdr[4:8] == b"ftyp"
            item.update({"status": "ok" if ok else "bad", "size": total_bytes,
                         "gear": gear, "path": path})
            if ok:
                task["ok_count"] += 1
            else:
                task["fail_count"] += 1
        except Exception as e:
            item.update({"status": "err", "err": f"{type(e).__name__}:{str(e)[:80]}"})
            task["fail_count"] += 1
        task["done_count"] = i + 1
        _save_tasks()
        time.sleep(1.5 + random.random() * 0.5)  # 主号低频
    task["status"] = "done"
    task["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_tasks()


@router.post("/v1/download")
def api_download(body: dict, x_api_key: str = Header("")):
    if x_api_key != config.API_KEY:
        return {"code": 401, "data": None, "meta": {"msg": "unauthorized"}}
    aids = [str(a) for a in (body.get("aweme_ids") or []) if str(a).strip()]
    if not aids:
        return {"code": 400, "data": None, "meta": {"msg": "aweme_ids 不能为空"}}
    task_id = _uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {"id": task_id, "aweme_ids": aids, "status": "queued",
                           "items": {}, "done_count": 0, "ok_count": 0, "fail_count": 0,
                           "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        _save_tasks()
    threading.Thread(target=_download_worker, args=(task_id,), daemon=True).start()
    return {"code": 0, "data": {"task_id": task_id, "queued": len(aids)}, "meta": {}}


@router.get("/v1/task/{task_id}")
def api_task(task_id: str, x_api_key: str = Header("")):
    if x_api_key != config.API_KEY:
        return {"code": 401, "data": None, "meta": {"msg": "unauthorized"}}
    with _tasks_lock:
        t = _tasks.get(task_id)
    if not t:
        return {"code": 404, "data": None, "meta": {"msg": "任务不存在"}}
    return {"code": 0, "data": t, "meta": {}}


_load_tasks()
