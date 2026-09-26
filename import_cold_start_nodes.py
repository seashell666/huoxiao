import sqlite3
import json
import time
import os

DB_PATH = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
DATA_DIR = r'F:\D\20-火枭\输出数据'

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 确保node_pool表存在
cursor.execute('''
CREATE TABLE IF NOT EXISTS node_pool (
    sec_uid TEXT PRIMARY KEY,
    nickname TEXT,
    score REAL DEFAULT 0.001,
    pool_level TEXT DEFAULT 'low',
    audit_status TEXT DEFAULT 'pending',
    created_at INTEGER,
    protect_until INTEGER,
    last_updated INTEGER,
    has_likes_open BOOLEAN DEFAULT 0,
    has_collects_open BOOLEAN DEFAULT 0,
    has_following_open BOOLEAN DEFAULT 0,
    is_private BOOLEAN DEFAULT 0
)
''')

now = int(time.time())
protect_until = now + 7 * 24 * 3600  # 7天保护期

added = 0
skipped = 0

# 1. 先导入others_collects_full.json里的28个用户
with open(os.path.join(DATA_DIR, 'others_collects_full.json'), 'r', encoding='utf-8') as f:
    others = json.load(f)

print(f'导入 others_collects_full.json 里的 {len(others)} 个用户...')

for user in others:
    sec_uid = user.get('sec_uid')
    nickname = user.get('nickname', '')
    
    if not sec_uid:
        continue
    
    # 这些用户收藏列表都是开的（不然我们也采不到）
    has_collects_open = 1
    
    # 检查是否已经存在
    cursor.execute('SELECT sec_uid FROM node_pool WHERE sec_uid = ?', (sec_uid,))
    if cursor.fetchone():
        skipped += 1
        continue
    
    # 插入
    cursor.execute('''
        INSERT INTO node_pool 
        (sec_uid, nickname, score, pool_level, audit_status, created_at, protect_until, last_updated, has_collects_open)
        VALUES (?, ?, 0.001, 'cooling', 'auto', ?, ?, ?, ?)
    ''', (sec_uid, nickname, now, protect_until, now, has_collects_open))
    added += 1

print(f'  新增: {added} 个，跳过: {skipped} 个')

# 2. 从ten_users_likes.json里提取视频作者作为新节点
with open(os.path.join(DATA_DIR, 'ten_users_likes.json'), 'r', encoding='utf-8') as f:
    videos = json.load(f)

print(f'\n从 ten_users_likes.json 的 {len(videos)} 个视频里提取作者...')

# 去重
author_sec_uids = set()
author_names = {}
for v in videos:
    sec = v.get('from_sec')
    name = v.get('from_user', '')
    if sec:
        author_sec_uids.add(sec)
        author_names[sec] = name

print(f'  去重后有 {len(author_sec_uids)} 个不同的作者')

added2 = 0
skipped2 = 0

for sec_uid in author_sec_uids:
    nickname = author_names.get(sec_uid, '')
    
    # 检查是否已经存在
    cursor.execute('SELECT sec_uid FROM node_pool WHERE sec_uid = ?', (sec_uid,))
    if cursor.fetchone():
        skipped2 += 1
        continue
    
    # 插入冷静池
    cursor.execute('''
        INSERT INTO node_pool 
        (sec_uid, nickname, score, pool_level, audit_status, created_at, protect_until, last_updated)
        VALUES (?, ?, 0.001, 'cooling', 'auto', ?, ?, ?)
    ''', (sec_uid, nickname, now, protect_until, now))
    added2 += 1

print(f'  新增: {added2} 个，跳过: {skipped2} 个')

conn.commit()

# 统计
cursor.execute('SELECT COUNT(*) as total FROM node_pool')
total = cursor.fetchone()['total']

cursor.execute("SELECT pool_level, COUNT(*) as cnt FROM node_pool GROUP BY pool_level")
print(f'\n节点池现在总共有 {total} 个节点:')
for row in cursor.fetchall():
    print(f'  {row["pool_level"]}: {row["cnt"]} 个')

conn.close()
print('\n✅ 导入完成！')
