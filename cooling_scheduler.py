# -*- coding: utf-8 -*-
"""冷静池自动采集调度器：低权重节点浅度采集"""
import sys, os, time, json
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")

import sqlite3
import huoxiao_client as hx

DB = r"F:\D\20-火枭\输出数据\huoxiao_cache.db"

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # 拿冷静池里最久没更新的节点
    c.execute("""SELECT sec_uid, nickname 
                 FROM node_pool 
                 WHERE pool_level='cooling' 
                 ORDER BY RANDOM()
                 LIMIT 3""")
    nodes = c.fetchall()
    print(f"本次采集 {len(nodes)} 个冷静池节点")
    
    guest = hx.GuestChannel()
    
    for sec, nick in nodes:
        print(f"\n=== 采集节点: {nick} ===")
        try:
            # 浅度采集：只拿喜欢列表第一页20个
            likes = guest.likes_app.get_page(sec, max_cursor="0", req_count="20")
            items = likes.get("aweme_list", [])
            print(f"  拿到 {len(items)} 个喜欢视频")
            
            # 存到数据库
            for item in items:
                aweme_id = item.get("aweme_id")
                desc = item.get("desc", "")
                digg_count = item.get("statistics", {}).get("digg_count", 0)
                cover = item.get("video", {}).get("cover", {}).get("url_list", [""])[0]
                play_url = item.get("video", {}).get("play_addr", {}).get("url_list", [""])[0]
                
                c.execute("""INSERT OR REPLACE INTO videos 
                             (aweme_id, sec_uid, desc, digg_count, cover_url, play_url, source_pool)
                             VALUES (?, ?, ?, ?, ?, ?, 'cooling')""",
                          (aweme_id, sec, desc, digg_count, cover, play_url))
            
            # 更新节点最后采集时间
            c.execute("UPDATE node_pool SET last_collect_time=? WHERE sec_uid=?",
                      (int(time.time()), sec))
            conn.commit()
            print(f"  ✅ 采集完成")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        
        # 每采完一个节点休息3秒，模拟人工操作
        time.sleep(3)
    
    conn.close()
    print("\n✅ 本次冷静池采集完成！")

if __name__ == "__main__":
    main()
