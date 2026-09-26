import sqlite3

conn = sqlite3.connect(r'F:\D\20-火枭\输出数据\huoxiao_cache.db')
cursor = conn.cursor()
cursor.execute("UPDATE node_pool SET is_blocked = 0, pool_level = 'outside' WHERE pool_level = 'blocked'")
print(f'恢复了 {cursor.rowcount} 个节点')
conn.commit()

cursor.execute("SELECT pool_level, COUNT(*) FROM node_pool GROUP BY pool_level")
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]} 个')

conn.close()
