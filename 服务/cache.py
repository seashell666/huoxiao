# -*- coding: utf-8 -*-
"""火枭缓存层 + 审计 + 面板统计

三层缓存语义（契约 v2.0 第三节）：
  A 类（TTL 7 天）：visibility / 用户信息 / 已采喜欢·收藏·关注·粉丝·发布列表
  B 类（TTL 1 小时）：detail 内容信号 / 视频直链
  C 类（不存）：评论 / cursor / 搜索

表结构：
  node_cache(sec_uid, dtype, payload_json, fetched_at, ttl)     —— A 类缓存
  video_cache(aweme_id, payload_json, fetched_at, ttl)          —— B 类缓存
  req_log(id, ts, endpoint, target, code, cached, channel, ms)  —— 全请求审计
  node_state(sec_uid, nickname, status, progress_json, updated_at) —— 节点进度（面板）
  daily_stats(date, key, value)                                 —— 按日聚合（面板时间维度）
"""
import io
import json
import os
import sqlite3
import time

import config


def _conn():
    os.makedirs(config.OUT, exist_ok=True)
    c = sqlite3.connect(config.CACHE_DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS node_cache(
        sec_uid TEXT NOT NULL,
        dtype   TEXT NOT NULL,          -- visibility / likes / collects / posts / following / follower
        payload_json TEXT NOT NULL,
        fetched_at INTEGER NOT NULL,
        ttl      INTEGER NOT NULL,
        PRIMARY KEY(sec_uid, dtype)
    );
    CREATE TABLE IF NOT EXISTS video_cache(
        aweme_id TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL,
        fetched_at INTEGER NOT NULL,
        ttl      INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS req_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        endpoint TEXT NOT NULL,
        target TEXT DEFAULT '',
        code INTEGER DEFAULT 0,
        cached INTEGER DEFAULT 0,
        channel TEXT DEFAULT 'guest',   -- guest / main / cache
        ms INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_reqlog_ts ON req_log(ts);
    CREATE TABLE IF NOT EXISTS node_state(
        sec_uid TEXT PRIMARY KEY,
        nickname TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',  -- pending/collecting/done/failed/cached/private
        progress_json TEXT DEFAULT '{}',-- {likes:50/50, collects:23/50, posts:0/12, visibility:1}
        updated_at INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS daily_stats(
        date TEXT NOT NULL,
        key TEXT NOT NULL,
        value INTEGER DEFAULT 0,
        PRIMARY KEY(date, key)
    );
    """)
    c.commit()
    c.close()


# ---------- A 类：节点缓存 ----------

def node_cache_get(sec_uid, dtype):
    c = _conn()
    row = c.execute(
        "SELECT payload_json, fetched_at, ttl FROM node_cache WHERE sec_uid=? AND dtype=?",
        (sec_uid, dtype)).fetchone()
    c.close()
    if not row:
        return None
    if time.time() - row["fetched_at"] > row["ttl"]:
        return None  # 过期，视为未命中
    return json.loads(row["payload_json"])


def node_cache_set(sec_uid, dtype, payload, ttl=None):
    if ttl is None:
        ttl = config.TTL_A
    c = _conn()
    c.execute(
        "INSERT OR REPLACE INTO node_cache(sec_uid, dtype, payload_json, fetched_at, ttl) VALUES(?,?,?,?,?)",
        (sec_uid, dtype, json.dumps(payload, ensure_ascii=False), int(time.time()), int(ttl)))
    c.commit()
    c.close()


# ---------- B 类：视频缓存 ----------

def video_cache_get(aweme_id):
    c = _conn()
    row = c.execute(
        "SELECT payload_json, fetched_at, ttl FROM video_cache WHERE aweme_id=?",
        (aweme_id,)).fetchone()
    c.close()
    if not row:
        return None
    if time.time() - row["fetched_at"] > row["ttl"]:
        return None
    return json.loads(row["payload_json"])


def video_cache_set(aweme_id, payload, ttl=None):
    if ttl is None:
        ttl = config.TTL_B
    c = _conn()
    c.execute(
        "INSERT OR REPLACE INTO video_cache(aweme_id, payload_json, fetched_at, ttl) VALUES(?,?,?,?)",
        (aweme_id, json.dumps(payload, ensure_ascii=False), int(time.time()), int(ttl)))
    c.commit()
    c.close()


# ---------- 审计 ----------

def log_req(endpoint, target="", code=0, cached=False, channel="guest", ms=0):
    c = _conn()
    c.execute(
        "INSERT INTO req_log(ts, endpoint, target, code, cached, channel, ms) VALUES(?,?,?,?,?,?,?)",
        (int(time.time()), endpoint, target, code, int(cached), channel, int(ms)))
    c.commit()
    c.close()
    # 按日聚合
    _daily_incr(time.strftime("%Y-%m-%d"), "req_total")
    if cached:
        _daily_incr(time.strftime("%Y-%m-%d"), "req_cached")
    if code == 0:
        _daily_incr(time.strftime("%Y-%m-%d"), "req_ok")
    else:
        _daily_incr(time.strftime("%Y-%m-%d"), "req_fail")


def _daily_incr(date, key, n=1):
    c = _conn()
    c.execute(
        "INSERT INTO daily_stats(date, key, value) VALUES(?,?,?) "
        "ON CONFLICT(date, key) DO UPDATE SET value = value + ?",
        (date, key, n, n))
    c.commit()
    c.close()


# ---------- 节点状态（面板节点卡） ----------

def node_update(sec_uid, nickname="", status=None, progress=None):
    c = _conn()
    row = c.execute("SELECT * FROM node_state WHERE sec_uid=?", (sec_uid,)).fetchone()
    if row is None:
        c.execute(
            "INSERT INTO node_state(sec_uid, nickname, status, progress_json, updated_at) VALUES(?,?,?,?,?)",
            (sec_uid, nickname, status or "pending", json.dumps(progress or {}), int(time.time())))
    else:
        pj = json.loads(row["progress_json"]) if row["progress_json"] else {}
        if progress:
            pj.update(progress)
        c.execute(
            "UPDATE node_state SET nickname=?, status=?, progress_json=?, updated_at=? WHERE sec_uid=?",
            (nickname or row["nickname"], status or row["status"],
             json.dumps(pj, ensure_ascii=False), int(time.time()), sec_uid))
    c.commit()
    c.close()


def node_list():
    c = _conn()
    rows = c.execute("SELECT * FROM node_state ORDER BY updated_at DESC LIMIT 500").fetchall()
    c.close()
    return [dict(r) for r in rows]


# ---------- P4 加固：主号预算 + 指数退避冷却 ----------

def main_budget_used():
    """今日主号已用请求数（生产禁止主号 → 预算内仅开发验真）"""
    c = _conn()
    r = c.execute("SELECT value FROM daily_stats WHERE date=? AND key='main_budget'",
                  (time.strftime("%Y-%m-%d"),)).fetchone()
    c.close()
    return r["value"] if r else 0


def main_budget_tick(n=1):
    """主号请求计数"""
    _daily_incr(time.strftime("%Y-%m-%d"), "main_budget", n)


def cooldown_set(key, backoff_base=5.0, fail_count=1):
    """标记冷却：下次可请求 = now + base * 2^(fail_count-1)（2096 指数退避）"""
    c = _conn()
    wait = backoff_base * (2 ** max(fail_count - 1, 0))
    c.execute(
        "INSERT OR REPLACE INTO video_cache(aweme_id, payload_json, fetched_at, ttl) VALUES(?,?,?,?)",
        (f"cd:{key}", f'{{"fail":{fail_count}}}', int(time.time()), int(wait)))
    c.commit()
    c.close()


def cooldown_wait(key):
    """返回距冷却结束剩余秒数（0=冷却结束）"""
    c = _conn()
    row = c.execute(
        "SELECT fetched_at, ttl FROM video_cache WHERE aweme_id=?", (f"cd:{key}",)).fetchone()
    c.close()
    if not row:
        return 0
    remain = row["ttl"] - (time.time() - row["fetched_at"])
    return int(remain) if remain > 0 else 0


# ---------- P4 干扰过滤 ----------

def interference_filter(items, min_len=8):
    """过滤防逆向干扰数据（空壳/无 desc/垃圾混淆）"""
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        desc = str(it.get("desc") or "").strip()
        if not desc:
            continue
        if len(desc) < min_len and not it.get("aweme_id"):
            continue
        out.append(it)
    return out


# ---------- 面板统计 ----------

def panel_overview():
    c = _conn()
    today = time.strftime("%Y-%m-%d")
    def stat(key, date=today):
        r = c.execute("SELECT value FROM daily_stats WHERE date=? AND key=?", (date, key)).fetchone()
        return r["value"] if r else 0
    # 缓存命中率
    total = stat("req_total")
    cached = stat("req_cached")
    ok = stat("req_ok")
    fail = stat("req_fail")
    # 冷却状态（最近 2096 次数）
    cool = c.execute(
        "SELECT COUNT(*) n FROM req_log WHERE code=2096 AND ts > ?", (int(time.time()) - 3600,)).fetchone()["n"]
    # 队列（占位，任务队列 P3 接入）
    ov = {
        "date": today,
        "req_total": total,
        "req_ok": ok,
        "req_fail": fail,
        "req_cached": cached,
        "cache_hit_rate": round(cached / total, 4) if total else 0,
        "cooling_1h": cool,
        "queue": 0,
        "nodes_active": c.execute("SELECT COUNT(*) n FROM node_state WHERE status NOT IN ('private','failed')").fetchone()["n"],
        "cache_db_mb": round(os.path.getsize(config.CACHE_DB) / 1048576, 2) if os.path.exists(config.CACHE_DB) else 0,
    }
    c.close()
    return ov


def panel_days(days=7):
    """近 N 天每日聚合（含今天，倒序）"""
    c = _conn()
    rows = {}
    for r in c.execute(
            "SELECT date, key, value FROM daily_stats WHERE date >= date('now', ?) ORDER BY date",
            (f"-{days} days",)).fetchall():
        rows.setdefault(r["date"], {})[r["key"]] = r["value"]
    c.close()
    out = []
    for d in sorted(rows.keys(), reverse=True):
        v = rows[d]
        total = v.get("req_total", 0)
        out.append({
            "date": d,
            "req_total": total,
            "req_ok": v.get("req_ok", 0),
            "req_fail": v.get("req_fail", 0),
            "req_cached": v.get("req_cached", 0),
            "cache_hit_rate": round(v.get("req_cached", 0) / total, 4) if total else 0,
        })
    return out


def panel_failures(limit=100):
    """失败清单：要了没给成功的"""
    c = _conn()
    rows = c.execute(
        "SELECT ts, endpoint, target, code FROM req_log WHERE code != 0 "
        "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def panel_hotkeys(limit=20):
    """反复调用热榜：按 target 聚合请求次数（提示该缓存）"""
    c = _conn()
    rows = c.execute(
        "SELECT target, COUNT(*) n, SUM(cached) c FROM req_log WHERE target != '' "
        "GROUP BY target ORDER BY n DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    out = []
    for r in rows:
        out.append({"target": r["target"], "times": r["n"], "cached": r["c"], "uncached": r["n"] - r["c"]})
    return out
