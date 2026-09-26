import json
import sqlite3
import time

DB_PATH = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
PRIVACY_FILE = r'F:\D\20-火枭\输出数据\temp\privacy_matrix_v4.json'

# 读隐私矩阵
with open(PRIVACY_FILE, 'r', encoding='utf-8') as f:
    privacy = json.load(f)

rows = privacy.get('rows', [])
print(f'隐私矩阵里有 {len(rows)} 个用户的可见性数据')

# 建一个字典，按sec_uid索引
privacy_map = {}
for row in rows:
    sec_uid = row.get('sec_uid')
    if sec_uid:
        privacy_map[sec_uid] = row

# 打开数据库
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 拿门外池里的所有节点
cursor.execute("SELECT * FROM node_pool WHERE pool_level = 'outside'")
nodes = cursor.fetchall()
print(f'门外池里有 {len(nodes)} 个节点')
print('---')

updated = 0
matched = 0
passed = 0
blocked = 0

for node in nodes:
    sec_uid = node['sec_uid']
    nickname = node['nickname'] or sec_uid[:15]
    
    if sec_uid in privacy_map:
        matched += 1
        p = privacy_map[sec_uid]
        
        # 喜欢列表可见性
        favorite = p.get('favorite', {})
        likes_verdict = favorite.get('verdict', 'unknown')
        has_likes_open = likes_verdict == 'open'
        
        # 收藏列表可见性
        collects = p.get('collects', {})
        collects_verdict = collects.get('verdict', 'unknown')
        has_collects_open = collects_verdict == 'open'
        
        # 关注列表可见性
        following = p.get('following', {})
        following_verdict = following.get('verdict', 'unknown')
        has_following_open = following_verdict == 'open'
        
        print(f'{nickname}: 喜欢={likes_verdict} 收藏={collects_verdict} 关注={following_verdict}')
        
        # 更新数据库
        cursor.execute('''
            UPDATE node_pool 
            SET has_likes_open = ?, has_collects_open = ?, has_following_open = ?, last_updated = ?
            WHERE sec_uid = ?
        ''', (
            1 if has_likes_open else 0,
            1 if has_collects_open else 0,
            1 if has_following_open else 0,
            int(time.time()),
            sec_uid
        ))
        updated += 1
        
        # 门槛：喜欢列表必须开
        if not has_likes_open:
            print(f'  → 喜欢列表没开，直接拉黑')
            cursor.execute('''
                UPDATE node_pool 
                SET is_blocked = 1, pool_level = 'blocked'
                WHERE sec_uid = ?
            ''', (sec_uid,))
            blocked += 1
        else:
            print(f'  → 通过')
            passed += 1
    else:
        print(f'{nickname}: 不在隐私矩阵里')

conn.commit()

print('---')
print(f'匹配到: {matched} 个')
print(f'更新: {updated} 个')
print(f'通过: {passed} 个')
print(f'拉黑: {blocked} 个')

# 统计现在的状态
cursor.execute("SELECT pool_level, COUNT(*) as cnt FROM node_pool GROUP BY pool_level")
print('\n现在各个池子的节点数：')
for row in cursor.fetchall():
    print(f'  {row["pool_level"]}: {row["cnt"]} 个')

conn.close()
