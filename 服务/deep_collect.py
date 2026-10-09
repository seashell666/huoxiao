# -*- coding: utf-8 -*-
"""潜龙深度采集 v2 —— 生产池节点 404 条喜欢视频「真深采」引擎

输入(唯一权威): F:\\D\\20-火枭\\输出数据\\node_likes_ownership.json
  - nodes[]   : 22 个节点(sec_uid/nickname/n_likes)
  - aid_nodes : {aid: [{sec_uid,nickname}, ...]} 404 条去重多对多(共408对,4条重合)
处理顺序 = JSON 中 aid 出现顺序。

每条 aid 做四件事:
  1. detail   游客通道 get_page_detail(raw) → _norm(含music) + bit_rate原画URL + play兜底URL
  2. comments 主号通道 1页20条 → comment_cache
  3. 归属    video_node_links(aid, sec_uid) 全节点对 INSERT OR IGNORE
  4. 下载    4线程 urllib: bit_rate原画→主目录 / play兜底→子目录 / 主号bitrate→子目录

复用跳过规则(b):
  - video_cache 已有 payload 且含 'music' 键, 且 comment_cache 已有该 aid
    → 跳过 detail+comments (计 detail_ok/comment_ok, 标注"复用已有")
  - 但下载仍要跑(这10条均无视频文件)

下载分级(f):
  ① bit_rate_url(1440优先,否则br[0]) → 主目录 {aid}.mp4
  ② 失败 → play_url_fallback(带水印) → 游客play兜底\\{aid}.mp4
  ③ 再失败 → 主号通道重取 detail bit_rate → 主号bitrate兜底\\{aid}.mp4
  - 旧文件复用: 输出数据\\视频下载\\{aid}.mp4 存在且>100KB 且 aid 不在 retry logs → 复制到主目录
  - 断点续跑: 主目录/两个兜底目录任一已有>100KB → 跳过
  - 每档重试2次; <100KB 视为失败; urllib(UA/Referer/timeout=120)

进度文件(g): F:\\D\\20-火枭\\输出数据\\deep_node_progress.json
  {total,done,detail_ok,comment_ok,download_ok,fail,current_aid,updated_at,started_at,
   detail_fail_list,comment_fail_list,download_fail_list}
  fail = 三个 fail_list 去重条数; 每完成一条或每≤60秒原子更新。

铁律: 单条失败不中断; 数据100%进库; 不删不改历史文件; 主号单线程;
      不动 huoxiao_client.py/config.py/cache.py。

用法: python deep_collect.py [--limit N 测试] [--comment_pages N 默认1]
"""
import sys, os, time, json, sqlite3, random, argparse
import threading, urllib.request, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")

from huoxiao_client import GuestChannel, AuthChannel, HuoxiaoClient, load_vault_cookie

# ---------- 路径常量 ----------
DB = r"F:\D\20-火枭\输出数据\huoxiao_cache.db"
INPUT_JSON = r"F:\D\20-火枭\输出数据\node_likes_ownership.json"
PROGRESS_FILE = r"F:\D\20-火枭\输出数据\deep_node_progress.json"
MAIN_DIR = r"F:\D\20-火枭\视频下载\节点深采"
PLAY_FB_DIR = os.path.join(MAIN_DIR, "游客play兜底")
MASTER_FB_DIR = os.path.join(MAIN_DIR, "主号bitrate兜底")
OLD_VIDEO_DIR = r"F:\D\20-火枭\输出数据\视频下载"
BATCH_DIR = r"F:\D\20-火枭\视频下载\批量原画"
LOG_FILE = os.path.join(MAIN_DIR, "_deep_collect.log")
OLD_RETRY_LOGS = [os.path.join(BATCH_DIR, "_retry.log"),
                  os.path.join(BATCH_DIR, "_retry_play.log")]

SLEEP_RANGE = (1.0, 2.0)
MIN_SIZE = 100 * 1024
DL_WORKERS = 4
DL_RETRY = 2          # 每档重试次数(共2次)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REFERER = "https://www.douyin.com/"

os.makedirs(MAIN_DIR, exist_ok=True)
os.makedirs(PLAY_FB_DIR, exist_ok=True)
os.makedirs(MASTER_FB_DIR, exist_ok=True)

# ---------- 全局状态(线程安全) ----------
_prog_lock = threading.Lock()
_db_lock = threading.Lock()        # 保护 worker 回填 video_cache
_guest_api_lock = threading.Lock() # 游客通道补取 bit_rate 必须串行节流(主号铁律同理)
_auth_api_lock = threading.Lock() # 主号通道兜底必须严格单线程

PROG = {}  # 进度文件内容
_prev_save_ts = 0.0


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def save_progress(force=False):
    """原子更新进度文件; force=True 立即写, 否则距上次≥60s才写"""
    global _prev_save_ts
    now = time.time()
    if not force and (now - _prev_save_ts) < 60:
        return
    with _prog_lock:
        PROG["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = PROGRESS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(PROG, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PROGRESS_FILE)
        _prev_save_ts = now


def ensure_tables(conn):
    c = conn.cursor()
    c.executescript(
        "CREATE TABLE IF NOT EXISTS comment_cache("
        " aid TEXT PRIMARY KEY,"
        " payload_json TEXT NOT NULL,"
        " fetched_at INTEGER NOT NULL);"
        "CREATE TABLE IF NOT EXISTS video_node_links("
        " aid TEXT NOT NULL,"
        " sec_uid TEXT NOT NULL,"
        " PRIMARY KEY(aid, sec_uid));"
    )
    conn.commit()


def load_targets(conn):
    """(a) 从 node_likes_ownership.json 读 404 条 aid(按JSON出现顺序) + 归属节点对"""
    with open(INPUT_JSON, encoding="utf-8") as f:
        d = json.load(f)
    aid_nodes = d["aid_nodes"]
    ordered = list(aid_nodes.keys())  # JSON 中 aid 出现顺序 = 处理顺序
    return ordered, aid_nodes


def already_have(conn, aid):
    """(b) 复用判断: video_cache 有 payload 且含 music, 且 comment_cache 有该 aid"""
    row = conn.execute(
        "SELECT payload_json FROM video_cache WHERE aweme_id=?", (aid,)).fetchone()
    if not row:
        return False
    try:
        pl = json.loads(row[0])
    except Exception:
        return False
    if "music" not in pl:
        return False
    crow = conn.execute("SELECT aid FROM comment_cache WHERE aid=?", (aid,)).fetchone()
    return bool(crow)


def pick_bitrate(aweme_detail):
    """(d) 从 raw aweme_detail 选最高档无水印原画 URL:
    优先 gear_name 含 '1440' 的 play_addr.url_list[0], 否则 br[0] 的。
    返回 (bit_url, gear_name, play_fallback)。"""
    v = aweme_detail.get("video") or {}
    br = v.get("bit_rate") or []
    bit_url = None
    gear = ""
    for b in br:
        if "1440" in str(b.get("gear_name") or ""):
            ul = (b.get("play_addr") or {}).get("url_list")
            if ul:
                bit_url = ul[0]
                gear = str(b.get("gear_name"))
                break
    if not bit_url and br:
        ul = (br[0].get("play_addr") or {}).get("url_list")
        if ul:
            bit_url = ul[0]
            gear = str(br[0].get("gear_name") or "")
    # play_url_fallback = video.play_addr.url_list[0] (带水印, 游客兜底下载用)
    play_fb = None
    ul = (v.get("play_addr") or {}).get("url_list")
    if ul:
        play_fb = ul[0]
    return bit_url, gear, play_fb


def old_retry_aids():
    """读历史 retry logs, 返回曾走 play 兜底/原画兜底的 aid 集合(这些旧文件可能带水印→禁止复用)"""
    s = set()
    for lp in OLD_RETRY_LOGS:
        try:
            with open(lp, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            # 日志里每行都会打 aid(19位数字)
            import re
            for m in re.findall(r"\b(\d{18,20})\b", txt):
                s.add(m)
        except Exception:
            pass
    return s


def download_url(url, dest_path):
    """urllib 下载, 重试 DL_RETRY 次; <100KB 视为失败。返回 bool。"""
    for attempt in range(DL_RETRY + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": REFERER})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < MIN_SIZE:
                raise ValueError(f"文件过小 {len(data)}B")
            with open(dest_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            log(f"    下载 {os.path.basename(dest_path)} 第{attempt+1}次失败: {str(e)[:70]}")
            time.sleep(2)
    return False


def fetch_bitrate_via_guest(guest, aid):
    """10条复用 aid 在 worker 里用游客通道补取 bit_rate_url, 串行节流。
    返回 (bit_url, gear, play_fb)。"""
    with _guest_api_lock:
        try:
            guest._guard(f"guest:detail:{aid}")
            j = guest.app.get_page_detail(aid)
            st = j.get("status_code")
            aw = j.get("aweme_detail") or {}
            if st != 0:
                guest._mark_fail(f"guest:detail:{aid}", st)
                return None, "", None
            return pick_bitrate(aw)
        except Exception as e:
            log(f"    游客补取 {aid} bit_rate 失败: {str(e)[:70]}")
            return None, "", None


def fetch_bitrate_via_auth(auth, aid):
    """③ 主号通道重取 detail 的 bit_rate(参考 retry_download_master.py), 严格单线程。"""
    with _auth_api_lock:
        try:
            j = auth.web_get("/aweme/v1/web/aweme/detail/",
                             {"aweme_id": aid},
                             f"https://www.douyin.com/video/{aid}")
            aw = j.get("aweme_detail") or {}
            v = aw.get("video") or {}
            br = v.get("bit_rate") or []
            bit_url = None
            gear = ""
            for b in br:
                if "1080" in str(b.get("gear_name") or ""):
                    ul = (b.get("play_addr") or {}).get("url_list")
                    if ul:
                        bit_url = ul[0]
                        gear = str(b.get("gear_name"))
                        break
            if not bit_url and br:
                ul = (br[0].get("play_addr") or {}).get("url_list")
                if ul:
                    bit_url = ul[0]
                    gear = str(br[0].get("gear_name") or "")
            return bit_url, gear
        except Exception as e:
            log(f"    主号兜底 {aid} 取 detail 失败: {str(e)[:70]}")
            return None, ""


def is_audio_payload(pl):
    """类型守卫: 无 bit_rate 视频档且播放地址是音频流(.mp3/ies-music) → 纯音频作品"""
    if pl.get("bit_rate_url"):
        return False
    v = pl.get("video") or {}
    pa = (v.get("play_addr") or {}).get("url_list") or []
    if not pa:
        return False
    u = pa[0]
    low = u.lower()
    return ".mp3" in low or "ies-music" in low or low.endswith(".m4a") or "music" in low


def do_download(aid, guest, auth, no_reuse_set):
    """单条 aid 的下载(在 worker 线程里跑)。返回 (ok:bool, source:str)。"""
    # 断点续跑: 主目录/两个兜底任一已有>100KB → 跳过
    for d in (MAIN_DIR, PLAY_FB_DIR, MASTER_FB_DIR):
        fp = os.path.join(d, aid + ".mp4")
        if os.path.exists(fp) and os.path.getsize(fp) > MIN_SIZE:
            return True, "断点已有"

    # 旧文件复用: 输出数据\视频下载\{aid}.mp4 存在且>100KB 且 aid 不在 retry logs
    old_fp = os.path.join(OLD_VIDEO_DIR, aid + ".mp4")
    if (os.path.exists(old_fp) and os.path.getsize(old_fp) > MIN_SIZE
            and aid not in no_reuse_set):
        try:
            shutil.copy2(old_fp, os.path.join(MAIN_DIR, aid + ".mp4"))
            return True, "复用旧文件"
        except Exception as e:
            log(f"    复用旧文件 {aid} 复制失败: {str(e)[:60]}, 改原画下载")

    # 读 video_cache payload 取 bit_rate_url / play_url_fallback
    bit_url = None
    gear = ""
    play_fb = None
    need_refill = False
    try:
        c = sqlite3.connect(DB)
        row = c.execute("SELECT payload_json FROM video_cache WHERE aweme_id=?", (aid,)).fetchone()
        c.close()
    except Exception:
        row = None
    if row:
        try:
            pl = json.loads(row[0])
            bit_url = pl.get("bit_rate_url")
            play_fb = pl.get("play_url_fallback")
            gear = pl.get("bit_rate_gear", "")
        except Exception:
            pl = {}
        else:
            # 类型守卫: 纯音频作品(无视频档) → 打标 media_type=audio, 绝不进视频下载队列
            if pl and pl.get("media_type") == "audio":
                return False, "音频作品(无视频流)"
            if not bit_url and pl and is_audio_payload(pl):
                try:
                    with _db_lock:
                        c = sqlite3.connect(DB)
                        c.execute("UPDATE video_cache SET payload_json=? WHERE aweme_id=?",
                                  (json.dumps({**pl, "media_type": "audio"}, ensure_ascii=False), aid))
                        c.commit()
                        c.close()
                except Exception:
                    pass
                return False, "音频作品(无视频流)"
            if not bit_url:
                need_refill = True  # 10条复用 aid 旧 payload 无 bit_rate_url
    else:
        need_refill = True

    if need_refill:
        bu, g, pf = fetch_bitrate_via_guest(guest, aid)
        bit_url = bit_url or bu
        gear = gear or g
        play_fb = play_fb or pf
        # 回填 video_cache payload 保持完整
        if bu:
            try:
                with _db_lock:
                    c = sqlite3.connect(DB)
                    row2 = c.execute("SELECT payload_json FROM video_cache WHERE aweme_id=?", (aid,)).fetchone()
                    if row2:
                        pl2 = json.loads(row2[0])
                        pl2["bit_rate_url"] = bu
                        pl2["bit_rate_gear"] = g
                        if pf:
                            pl2["play_url_fallback"] = pf
                        c.execute("UPDATE video_cache SET payload_json=? WHERE aweme_id=?",
                                  (json.dumps(pl2, ensure_ascii=False), aid))
                        c.commit()
                    c.close()
            except Exception as e:
                log(f"    回填 {aid} bit_rate_url 失败: {str(e)[:60]}")

    # ① bit_rate_url → 主目录
    if bit_url:
        dest = os.path.join(MAIN_DIR, aid + ".mp4")
        if download_url(bit_url, dest):
            return True, f"原画{gear}"
        log(f"    ① 原画 {aid} 失败, 转 play 兜底")

    # ② play_url_fallback → 游客play兜底\
    if play_fb:
        dest = os.path.join(PLAY_FB_DIR, aid + ".mp4")
        if download_url(play_fb, dest):
            return True, "游客play兜底"
        log(f"    ② play兜底 {aid} 失败, 转主号bitrate兜底")

    # ③ 主号通道重取 bit_rate → 主号bitrate兜底\
    m_url, m_gear = fetch_bitrate_via_auth(auth, aid)
    if m_url:
        dest = os.path.join(MASTER_FB_DIR, aid + ".mp4")
        if download_url(m_url, dest):
            return True, f"主号{m_gear}"
        log(f"    ③ 主号兜底 {aid} 也失败")

    return False, "彻底失败"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多采 N 条视频后退出(0=全量)")
    ap.add_argument("--comment_pages", type=int, default=1, help="评论翻页数(默认1页20条; 本引擎固定1页)")
    args = ap.parse_args()

    ck = load_vault_cookie()
    if not ck:
        print("❌ vault 无 cookie，评论主号通道不可用，退出")
        return
    guest = GuestChannel(min_interval=1.5)
    auth = AuthChannel(ck, min_interval=5.0)

    conn = sqlite3.connect(DB)
    ensure_tables(conn)
    ordered, aid_nodes = load_targets(conn)
    total = len(ordered)
    if args.limit:
        ordered = ordered[:args.limit]
    total_run = len(ordered)

    # 初始化进度文件
    global PROG
    PROG = {
        "total": total,           # JSON 里 404 条总数(不受 limit 影响)
        "done": 0,
        "detail_ok": 0,
        "comment_ok": 0,
        "download_ok": 0,
        "fail": 0,
        "current_aid": "",
        "updated_at": "",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "detail_fail_list": [],
        "comment_fail_list": [],
        "download_fail_list": [],
    }
    save_progress(force=True)

    log(f"待深采视频: {total_run} 条(JSON总数{total}, limit={args.limit or '全量'})")
    log(f"输出主目录: {MAIN_DIR}")

    no_reuse = old_retry_aids()
    log(f"历史 retry logs 命中 aid {len(no_reuse)} 个(禁止旧文件复用)")

    # ========== 阶段1: detail + comments + 归属 (严格串行, 主号单线程铁律) ==========
    for i, aid in enumerate(ordered, 1):
        PROG["current_aid"] = aid
        save_progress()

        # (c) 归属表: 每条 aid(含跳过的) 把 aid_nodes[aid] 全部节点对 INSERT OR IGNORE
        pairs = aid_nodes.get(aid, [])
        try:
            c = conn.cursor()
            c.executemany(
                "INSERT OR IGNORE INTO video_node_links(aid, sec_uid) VALUES(?,?)",
                [(aid, p["sec_uid"]) for p in pairs])
            conn.commit()
        except Exception as e:
            log(f"[{i}/{total_run}] ⚠️ 归属 {aid} 落库失败: {str(e)[:60]}")

        # (b) 复用判断
        reuse = already_have(conn, aid)
        if reuse:
            PROG["detail_ok"] += 1
            PROG["comment_ok"] += 1
            log(f"[{i}/{total_run}] ♻️ {aid} 复用已有 detail+comments ({len(pairs)}节点对)")
        else:
            # (d) detail 游客通道, 直接取 raw
            try:
                guest._guard(f"guest:detail:{aid}")
                j = guest.app.get_page_detail(aid)
                st = j.get("status_code")
                aw = j.get("aweme_detail") or {}
                if st == 0 and aw:
                    payload = HuoxiaoClient._norm(aw, detail=True)  # 含 music 键
                    bit_url, gear, play_fb = pick_bitrate(aw)
                    payload["bit_rate_url"] = bit_url
                    payload["bit_rate_gear"] = gear
                    payload["play_url_fallback"] = play_fb
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO video_cache(aweme_id,payload_json,fetched_at,ttl) VALUES(?,?,?,?)",
                              (aid, json.dumps(payload, ensure_ascii=False), int(time.time()), 7 * 86400))
                    conn.commit()
                    PROG["detail_ok"] += 1
                    log(f"[{i}/{total_run}] ✅ detail {aid} 「{(payload.get('desc') or '')[:18]}」 {gear or 'no_gear'}")
                else:
                    guest._mark_fail(f"guest:detail:{aid}", st)
                    PROG["detail_fail_list"].append(aid)
                    PROG["fail"] = len(set(PROG["detail_fail_list"]) | set(PROG["comment_fail_list"]) | set(PROG["download_fail_list"]))
                    log(f"[{i}/{total_run}] ⚠️ detail {aid} status_code={st}")
            except Exception as e:
                PROG["detail_fail_list"].append(aid)
                PROG["fail"] = len(set(PROG["detail_fail_list"]) | set(PROG["comment_fail_list"]) | set(PROG["download_fail_list"]))
                log(f"[{i}/{total_run}] ❌ detail {aid} {type(e).__name__}: {str(e)[:70]}")

            # (e) comments 主号通道 1 页
            try:
                items, more, cur, meta = auth.get_comments(aid, cursor=0, count=20)
                if meta.get("status") == 0:
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO comment_cache(aid,payload_json,fetched_at) VALUES(?,?,?)",
                              (aid, json.dumps(items, ensure_ascii=False), int(time.time())))
                    conn.commit()
                    PROG["comment_ok"] += 1
                    log(f"    💬 comments {aid} {len(items)}条")
                else:
                    PROG["comment_fail_list"].append(aid)
                    PROG["fail"] = len(set(PROG["detail_fail_list"]) | set(PROG["comment_fail_list"]) | set(PROG["download_fail_list"]))
                    log(f"    ⚠️ comments {aid} meta={meta}")
            except Exception as e:
                PROG["comment_fail_list"].append(aid)
                PROG["fail"] = len(set(PROG["detail_fail_list"]) | set(PROG["comment_fail_list"]) | set(PROG["download_fail_list"]))
                log(f"    ❌ comments {aid} {type(e).__name__}: {str(e)[:70]}")

            time.sleep(random.uniform(*SLEEP_RANGE))

        PROG["done"] = i
        save_progress()

    # ========== 阶段2: 下载 (4 线程并行; 主号兜底/游客补取已加锁串行) ==========
    log(f"=== 阶段2: 开始下载 {total_run} 条 (并发{DL_WORKERS}) ===")
    with ThreadPoolExecutor(max_workers=DL_WORKERS) as ex:
        futs = {ex.submit(do_download, aid, guest, auth, no_reuse): aid for aid in ordered}
        done_dl = 0
        for fut in as_completed(futs):
            aid = futs[fut]
            done_dl += 1
            PROG["current_aid"] = f"[下载{done_dl}/{total_run}] {aid}"
            try:
                ok, source = fut.result()
            except Exception as e:
                ok, source = False, f"异常:{type(e).__name__}"
            if ok:
                PROG["download_ok"] += 1
                log(f"[下载{done_dl}/{total_run}] ✅ {aid} <- {source}")
            elif source == "音频作品(无视频流)":
                PROG["audio_skip"] = PROG.get("audio_skip", 0) + 1
                log(f"[下载{done_dl}/{total_run}] 🎵 {aid} <- 音频作品(无视频流,已守卫)")
            else:
                PROG["download_fail_list"].append(aid)
                log(f"[下载{done_dl}/{total_run}] ❌ {aid} <- {source}")
            PROG["fail"] = len(set(PROG["detail_fail_list"]) | set(PROG["comment_fail_list"]) | set(PROG["download_fail_list"]))
            save_progress()

    conn.close()
    PROG["current_aid"] = "完成"
    save_progress(force=True)
    log(f"=== 全部结束: detail_ok={PROG['detail_ok']} comment_ok={PROG['comment_ok']} "
        f"download_ok={PROG['download_ok']} fail={PROG['fail']} "
        f"(detail_fail={len(PROG['detail_fail_list'])} comment_fail={len(PROG['comment_fail_list'])} "
        f"download_fail={len(PROG['download_fail_list'])}) ===")


if __name__ == "__main__":
    main()
