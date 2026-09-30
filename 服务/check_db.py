import sqlite3

conn = sqlite3.connect(r'F:\D\20-火枭\输出数据\huoxiao_cache.db')
cursor = conn.cursor()

# 表列表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('表列表：')
for t in tables:
    print(' -', t[0])

print('\n---\n')

# 每个表的字段
for t in tables:
    table_name = t[0]
    print(f'\n表 {table_name} 的字段：')
    cursor.execute(f'PRAGMA table_info({table_name})')
    for col in cursor.fetchall():
        print(f'  - {col[1]} ({col[2]})')

conn.close()
