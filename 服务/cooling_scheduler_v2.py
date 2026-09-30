# -*- coding: utf-8 -*-
"""冷静池自动采集调度器 v2 —— 以节点为单位

核心逻辑（火枭核心产品逻辑）：
- 队列：cooling 池按 last_collect_time ASC（最久未更新优先，NULL 排最前）
- 节点为单位：一个节点进来，一次性把它的浅层数据采完再采下一个
  （冷静池浅层策略：只拿喜欢列表 2 页≈40 条，不进入视频详情，外面蹭一蹭不进去）
- 防抖：节点间 3-5s 随机间隔模拟人工；每批 5 个；批间 90s
- 落库：video_cache（视频明细）+ node_cache（likes 面板格式）+ node_pool.last_collect_time
- 失败：单个节点出错不中断整批；closed 判定为未公开则标记 blocked

用法: python cooling_scheduler_v2.py [--batch 5] [--limit 0=全量]
"""
import sys, os, time, json, sqlite3, random, argparse

sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")

from huoxiao_client import GuestChannel

DB = r"F:\D\20-火枭\输出数据\huoxiao_cache.db"
NODE_GAP = (3, 5)      # 节点间随机间隔
BATCH_GAP = 90         # 批间休息


def get_queue(c, limit, max_collect):
    """最久未更新优先（含从未采过的）"""
    c.execute("""SELECT sec_uid, nickname, has_likes_open, is_private
                 FROM node_pool
                 WHERE pool_level='cooling' AND is_blocked=0
                   AND (last_collect_time IS NULL OR last_collect_time < ?)
                 ORDER BY last_collect_time ASC NULLS FIRST, sec_uid
                 LIMIT ?""", (int(time.time()) - max_collect, limit))
    return c.fetchall()


def save_node(conn, sec, items):
    """落库：video_cache + node_cache(likes 面板格式)"""
    c = conn.cursor()
    now = int(time.time())
    n = 0
    panel = []
    for it in items:
        aid = it.get("aweme_id") or ""
        if not aid:
            continue
        cover = it.get("cover") or ""
        stats = it.get("stats") or {}
        au = it.get("author") or {}
        c.execute("INSERT OR REPLACE INTO video_cache (aweme_id, payload_json, fetched_at, ttl) VALUES (?,?,?,?)",
                  (aid, json.dumps(it, ensure_ascii=False), now, 7 * 86400))
        panel.append({
            "aweme_id": aid,
            "cover_url": cover,
            "digg_count": stats.get("digg", 0),
            "share_url": f"https://www.douyin.com/video/{aid}",
            "desc": it.get("desc", ""),
            "author_name": au.get("nickname", ""),
            "author_avatar": au.get("avatar", ""),
        })
        n += 1
    if panel:
        c.execute("INSERT OR REPLACE INTO node_cache (sec_uid, dtype, payload_json, fetched_at, ttl) VALUES (?,?,?,?,?)",
                  (sec, "likes", json.dumps(panel, ensure_ascii=False), now, 7 * 86400))
    c.execute("UPDATE node_pool SET last_collect_time=? WHERE sec_uid=?", (now, sec))
    conn.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=5, help="每批节点数")
    ap.add_argument("--max_collect", type=int, default=7 * 86400, help="多久内采过的不再采(秒)")
    args = ap.parse_args()

    guest = GuestChannel(min_interval=1.5)
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # 统计待采队列
    c.execute("""SELECT COUNT(*) FROM node_pool
                 WHERE pool_level='cooling' AND is_blocked=0
                   AND (last_collect_time IS NULL OR last_collect_time < ?)""",
              (int(time.time()) - args.max_collect,))
    pending = c.fetchone()[0]
    print(f"冷静池待采节点: {pending} 个（每批 {args.batch}，批间 {BATCH_GAP}s）")

    done = 0
    fail = 0
    while True:
        queue = get_queue(c, args.batch, args.max_collect)
        if not queue:
            print("\n队列已空，全部冷却节点已采集完毕，退出")
            break
        for sec, nick, likes_open, is_private in queue:
            nick = nick or sec[:12]
            print(f"\n=== 节点[{done+fail+1}]: {nick} ===", flush=True)
            # 已有判定：喜欢关闭/私密 → 拉黑跳过
            if is_private or likes_open == 0:
                c.execute("UPDATE node_pool SET is_blocked=1, pool_level='blocked', audit_status='blocked' WHERE sec_uid=?", (sec,))
                conn.commit()
                print(f"  ⏭️ 已判定无资格(喜欢{'关' if likes_open==0 else '?'}/私密)，拉黑", flush=True)
                continue
            try:
                items, _, _, meta = guest.get_likes(sec, count=20, max_pages=2)
                if meta.get("closed"):
                    c.execute("UPDATE node_pool SET is_blocked=1, pool_level='blocked', audit_status='blocked', has_likes_open=0 WHERE sec_uid=?", (sec,))
                    conn.commit()
                    print(f"  ⏭️ 喜欢未公开，拉黑", flush=True)
                    continue
                n = save_node(conn, sec, items)
                done += 1
                print(f"  ✅ 保存 {n} 条喜欢 (dict: {meta.get('status')})", flush=True)
            except Exception as e:
                fail += 1
                print(f"  ❌ {type(e).__name__}: {str(e)[:120]}", flush=True)
            time.sleep(random.uniform(*NODE_GAP))
        print(f"\n-- 本批完成(成功{done}/失败{fail})，休息 {BATCH_GAP}s --", flush=True)
        time.sleep(BATCH_GAP)

    conn.close()
    print(f"\n✅ 全部完成：成功 {done} 个节点，失败 {fail}")


if __name__ == "__main__":
    main()
