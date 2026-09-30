import sqlite3
import time
import requests

DB_PATH = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
API_BASE = "http://127.0.0.1:8100"
API_KEY = "huoxiao-2026"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 先把刚才误拉黑的恢复
cursor.execute("UPDATE node_pool SET is_blocked = 0, pool_level = 'outside' WHERE pool_level = 'blocked'")
print(f'恢复了 {cursor.rowcount} 个误拉黑的节点')
conn.commit()

# 现在拿门外池里的节点
cursor.execute("SELECT * FROM node_pool WHERE pool_level = 'outside' AND is_blocked = 0")
nodes = cursor.fetchall()
print(f'门外池里现在有 {len(nodes)} 个节点，重新做可见性判定（这次看喜欢列表）...')
print('---')

passed = 0
blocked = 0
failed = 0

for i, node in enumerate(nodes):
    sec_uid = node['sec_uid']
    nickname = node['nickname'] or sec_uid[:15]
    
    print(f'[{i+1}/{len(nodes)}] 检查 {nickname}...', end=' ', flush=True)
    
    try:
        # 调用火枭的可见性接口
        resp = requests.get(
            f"{API_BASE}/v1/user/{sec_uid}/visibility",
            headers={"X-Api-Key": API_KEY},
            timeout=30
        )
        data = resp.json().get('data', {})
        
        # 门槛：喜欢列表必须开
        # 现在先看返回里有没有likes字段
        has_likes = data.get('likes', 'unknown')
        
        print(f'喜欢: {has_likes}')
        
        # 不符合的直接拉黑
        if has_likes != 'open':
            print(f'  → 喜欢列表没开，直接拉黑')
            cursor.execute('''
                UPDATE node_pool 
                SET is_blocked = 1, pool_level = 'blocked', last_updated = ?
                WHERE sec_uid = ?
            ''', (int(time.time()), sec_uid))
            blocked += 1
        else:
            print(f'  → 通过')
            cursor.execute('''
                UPDATE node_pool 
                SET has_likes_open = 1, last_updated = ?
                WHERE sec_uid = ?
            ''', (int(time.time()), sec_uid))
            passed += 1
        
        conn.commit()
        
    except Exception as e:
        print(f'失败: {e}')
        failed += 1
    
    # 像人一样，每个节点之间稍微停一下
    time.sleep(1)

print('---')
print(f'完成！通过: {passed}，拉黑: {blocked}，失败: {failed}')

# 统计
cursor.execute("SELECT pool_level, COUNT(*) as cnt FROM node_pool GROUP BY pool_level")
print('\n现在各个池子的节点数：')
for row in cursor.fetchall():
    print(f'  {row["pool_level"]}: {row["cnt"]} 个')

conn.close()
