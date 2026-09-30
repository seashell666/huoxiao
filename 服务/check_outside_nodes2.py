import sqlite3
import time
import requests

DB_PATH = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
API_BASE = "http://127.0.0.1:8100"
API_KEY = "huoxiao-2026"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 先把cooling改成outside
cursor.execute("UPDATE node_pool SET pool_level = 'outside' WHERE pool_level = 'cooling'")
print(f'把 {cursor.rowcount} 个节点从冷静池移到门外池')
conn.commit()

# 现在拿门外池里的节点
cursor.execute("SELECT * FROM node_pool WHERE pool_level = 'outside'")
nodes = cursor.fetchall()
print(f'门外池里现在有 {len(nodes)} 个节点，开始做可见性判定...')
print('---')

passed = 0
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
        
        has_collects = data.get('collects') == 'open'
        
        print(f'收藏: {data.get("collects", "?")}')
        
        # 更新到数据库
        cursor.execute('''
            UPDATE node_pool 
            SET has_collects_open = ?, last_updated = ?
            WHERE sec_uid = ?
        ''', (1 if has_collects else 0, int(time.time()), sec_uid))
        conn.commit()
        
        passed += 1
        
    except Exception as e:
        print(f'失败: {e}')
        failed += 1
    
    # 像人一样，每个节点之间稍微停一下
    time.sleep(1)

print('---')
print(f'完成！成功: {passed}，失败: {failed}')

conn.close()
