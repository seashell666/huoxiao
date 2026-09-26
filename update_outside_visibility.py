# -*- coding: utf-8 -*-
"""门外池节点可见性更新：同时判断收藏+喜欢两个列表"""
import sys, os
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")

import sqlite3
import huoxiao_client as hx

DB = r"F:\D\20-火枭\输出数据\huoxiao_cache.db"

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # 拿所有门外池的节点
    c.execute("SELECT sec_uid, nickname FROM node_pool WHERE pool_level='outside'")
    nodes = c.fetchall()
    print(f"门外池共 {len(nodes)} 个节点")
    
    guest = hx.GuestChannel()
    
    for i, (sec, nick) in enumerate(nodes):
        print(f"\n[{i+1}/{len(nodes)}] {nick}")
        try:
            vis = guest.visibility(sec)
            print(f"  收藏: {vis.get('collects')}, 喜欢: {vis.get('likes')}, 私密: {vis.get('is_private')}")
            
            # 更新数据库
            c.execute("""UPDATE node_pool 
                         SET has_likes_open = ?, has_collects_open = ?, is_private = ?,
                             pool_level = CASE WHEN has_likes_open = 1 THEN 'cooling' ELSE 'blocked' END
                         WHERE sec_uid = ?""",
                      (1 if vis.get('likes') == 'open' else 0,
                       1 if vis.get('collects') == 'open' else 0,
                       1 if vis.get('is_private') else 0,
                       sec))
            conn.commit()
        except Exception as e:
            print(f"  错误: {e}")
    
    # 统计结果
    c.execute("SELECT pool_level, COUNT(*) FROM node_pool GROUP BY pool_level")
    print("\n=== 最终池子分布 ===")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}个")
    
    conn.close()

if __name__ == "__main__":
    main()
