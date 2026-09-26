import sqlite3
import json

conn = sqlite3.connect(r'F:\D\20-火枭\输出数据\huoxiao_cache.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 看看node_state表里有多少节点
cursor.execute("SELECT COUNT(*) as total FROM node_state")
total = cursor.fetchone()['total']
print(f'node_state表里总共有 {total} 个节点')

print('\n---\n')

# 看看这些节点的状态
cursor.execute("SELECT status, COUNT(*) as cnt FROM node_state GROUP BY status")
print('节点状态分布：')
for row in cursor.fetchall():
    print(f'  {row["status"]}: {row["cnt"]} 个')

print('\n---\n')

# 看看前20个节点的详情
cursor.execute("SELECT * FROM node_state ORDER BY updated_at DESC LIMIT 20")
print('最近更新的20个节点：')
for row in cursor.fetchall():
    progress = json.loads(row['progress_json']) if row['progress_json'] else {}
    print(f'  {row["nickname"] or row["sec_uid"][:15]}... | 状态: {row["status"]} | 可见性: {progress.get("visibility", "?")} | 喜欢: {progress.get("likes", "?")} | 收藏: {progress.get("collects", "?")}')

print('\n---\n')

# 看看node_cache里有什么类型的数据
cursor.execute("SELECT dtype, COUNT(*) as cnt FROM node_cache GROUP BY dtype")
print('缓存数据类型分布：')
for row in cursor.fetchall():
    print(f'  {row["dtype"]}: {row["cnt"]} 条')

print('\n---\n')

# 看看video_cache里有多少视频
cursor.execute("SELECT COUNT(*) as total FROM video_cache")
video_total = cursor.fetchone()['total']
print(f'video_cache里有 {video_total} 个视频详情')

conn.close()
