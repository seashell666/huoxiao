import sqlite3
import requests
import json
import os

DB_PATH = r"F:\D\20-火枭\输出数据\huoxiao_cache.db"
API_BASE = "http://127.0.0.1:8100"
API_KEY = "huoxiao-2026"

# 1. 从数据库拿27个冷静池节点
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT sec_uid, nickname, has_likes_open, has_collects_open FROM node_pool WHERE pool_level='cooling' AND is_blocked=0")
nodes = [dict(r) for r in cur.fetchall()]
conn.close()

print(f"拿到{len(nodes)}个冷静池节点")

# 2. 给每个节点拉浅度数据：用户主页+喜欢列表前9个
results = []
for node in nodes:
    sec_uid = node['sec_uid']
    print(f"正在采集: {node['nickname']}...")
    
    # 拉用户主页
    try:
        r = requests.get(f"{API_BASE}/api/v1/user/{sec_uid}/profile", 
                        headers={"X-Api-Key": API_KEY}, timeout=15)
        profile = r.json() if r.status_code == 200 else {}
    except:
        profile = {}
    
    # 拉喜欢列表前9个
    try:
        r = requests.get(f"{API_BASE}/api/v1/user/{sec_uid}/likes?count=9",
                        headers={"X-Api-Key": API_KEY}, timeout=15)
        likes = r.json() if r.status_code == 200 else {"list": []}
    except:
        likes = {"list": []}
    
    results.append({
        "sec_uid": sec_uid,
        "nickname": node['nickname'],
        "profile": profile,
        "likes": likes.get('list', [])[:9]
    })

# 3. 保存成JSON
with open(r"F:\D\20-火枭\输出数据\cooling_nodes_preview.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"全部采集完成！共{len(results)}个节点，数据已保存")
