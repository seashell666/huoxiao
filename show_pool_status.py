import sqlite3

conn = sqlite3.connect(r'F:\D\20-火枭\输出数据\huoxiao_cache.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 看看各个池子的数量
cursor.execute("SELECT pool_level, COUNT(*) as cnt FROM node_pool GROUP BY pool_level")
print('各个池子的节点数：')
for row in cursor.fetchall():
    print(f'  {row["pool_level"]}: {row["cnt"]} 个')

print('\n---\n')

# 看看门外池里的可见性情况
cursor.execute("SELECT * FROM node_pool WHERE pool_level = 'outside'")
nodes = cursor.fetchall()
print(f'门外池里 {len(nodes)} 个节点：')
for node in nodes:
    collects = '✓收藏开' if node['has_collects_open'] else '✗收藏关'
    print(f'  {node["nickname"] or node["sec_uid"][:15]}... | {collects}')

conn.close()
