# -*- coding: utf-8 -*-
"""节点采集调度器 v2 —— 以节点为单位（主号通道版，覆盖冷静池+生产池）

核心逻辑（火枭核心产品逻辑）：
- 队列：cooling + low（生产池）按 last_collect_time ASC（最久未更新优先，NULL 排最前）
- 节点为单位：一个节点进来，一次性把它的浅层数据采完再采下一个
  （浅层策略：只拿喜欢列表 2 页≈40 条，不进入视频详情，外面蹭一蹭不进去）
- 通道：喜欢列表走【主号 Web 通道】（用户 2026-09-30 拍板；
  游客通道拿不到 likes——签名锁，早已验证是空壳）
- 预算：主号日 50000 / 滑动 2h 7000（config.MAIN_DAILY_BUDGET / MAIN_2H_BUDGET，
  huoxiao_client._guard 内生效）
- 防抖：节点间 3-5s 随机间隔模拟人工；每批 5 个；批间 90s
- 落库：video_cache（视频明细）+ node_cache（likes 面板格式）+ node_pool.last_collect_time
- 失败：单个节点出错不中断整批；喜欢未公开(3002279) 判定为无资格则标记 blocked
- 防死循环：本轮已处理过的节点不再处理（seen 集合）——
  修 2026-09-30 试跑暴露的 bug：--max_collect 0 强制模式下同批节点无限重复采

用法: python cooling_scheduler_v2.py [--batch 5] [--max_collect 0=强制一轮] [--limit N=最多采N个]
"""
import sys, os, time, json, sqlite3, random, argparse

sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")

from huoxiao_client import AuthChannel, load_vault_cookie

DB = r"F:\D\20-火枭\输出数据\huoxiao_cache.db"
NODE_GAP = (3, 5)      # 节点间随机间隔
BATCH_GAP = 90         # 批间休息
LIKES_CLOSED = 3002279 # 抖音状态码：喜欢列表未公开


def get_queue(c, limit, max_collect):
    """最久未更新优先（含从未采过的）；覆盖冷静池 + 生产池(low)"""
    c.execute("""SELECT sec_uid, nickname, has_likes_open, is_private, pool_level
                 FROM node_pool
                 WHERE pool_level IN ('cooling','low') AND is_blocked=0
                   AND (last_collect_time IS NULL OR last_collect_time < ?)
                 ORDER BY last_collect_time ASC NULLS FIRST, sec_uid
                 LIMIT ?""", (int(time.time()) - max_collect, limit))
    return c.fetchall()


def fetch_likes(auth, sec):
    """主号通道翻 2 页拿喜欢列表；返回 (items, closed_flag)"""
    items_all = []
    cursor = 0
    for _ in range(2):
        items, has_more, cursor, meta = auth.get_likes(sec, cursor=cursor, count=20)
        if meta.get("status") == LIKES_CLOSED:
            return [], True
        if meta.get("status") != 0:
            break
        items_all.extend(items)
        if not has_more:
            break
    return items_all, False


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
    ap.add_argument("--max_collect", type=int, default=7 * 86400, help="多久内采过的不再采(秒)，0=强制采一轮")
    ap.add_argument("--limit", type=int, default=0, help="最多采 N 个节点后退出，0=全量")
    args = ap.parse_args()

    ck = load_vault_cookie()
    if not ck:
        print("❌ vault 无 cookie，主号通道不可用，退出")
        return
    auth = AuthChannel(ck, min_interval=5.0)

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # 统计待采队列
    c.execute("""SELECT COUNT(*) FROM node_pool
                 WHERE pool_level IN ('cooling','low') AND is_blocked=0
                   AND (last_collect_time IS NULL OR last_collect_time < ?)""",
              (int(time.time()) - args.max_collect,))
    pending = c.fetchone()[0]
    print(f"待采节点: {pending} 个（每批 {args.batch}，批间 {BATCH_GAP}s，通道=主号Web，limit={args.limit or '全量'}）")

    done = 0
    fail = 0
    seen = set()   # 本轮已处理节点，防死循环
    while True:
        if args.limit and done + fail >= args.limit:
            print(f"\n已达 --limit {args.limit}，提前退出")
            break
        queue = get_queue(c, args.batch, args.max_collect)
        queue = [q for q in queue if q[0] not in seen]
        if not queue:
            print("\n队列已空，全部节点已采集完毕，退出")
            break
        for sec, nick, likes_open, is_private, pool in queue:
            seen.add(sec)
            nick = nick or sec[:12]
            pool_name = "生产池" if pool == "low" else "冷静池"
            print(f"\n=== 节点[{done+fail+1}]({pool_name}): {nick} ===", flush=True)
            # 已有判定：喜欢关闭/私密 → 拉黑跳过
            if is_private or likes_open == 0:
                c.execute("UPDATE node_pool SET is_blocked=1, pool_level='blocked', audit_status='blocked' WHERE sec_uid=?", (sec,))
                conn.commit()
                print(f"  ⏭️ 已判定无资格(喜欢{'关' if likes_open==0 else '?'}/私密)，拉黑", flush=True)
                continue
            try:
                items, closed = fetch_likes(auth, sec)
                if closed:
                    c.execute("UPDATE node_pool SET is_blocked=1, pool_level='blocked', audit_status='blocked', has_likes_open=0 WHERE sec_uid=?", (sec,))
                    conn.commit()
                    print(f"  ⏭️ 喜欢未公开，拉黑", flush=True)
                    continue
                n = save_node(conn, sec, items)
                done += 1
                print(f"  ✅ 保存 {n} 条喜欢 (主号通道)", flush=True)
            except Exception as e:
                fail += 1
                print(f"  ❌ {type(e).__name__}: {str(e)[:120]}", flush=True)
            time.sleep(random.uniform(*NODE_GAP))
            if args.limit and done + fail >= args.limit:
                print(f"\n已达 --limit {args.limit}，提前退出", flush=True)
                conn.close()
                return
        print(f"\n-- 本批完成(成功{done}/失败{fail})，休息 {BATCH_GAP}s --", flush=True)
        time.sleep(BATCH_GAP)

    conn.close()
    print(f"\n✅ 全部完成：成功 {done} 个节点，失败 {fail}")


if __name__ == "__main__":
    main()
