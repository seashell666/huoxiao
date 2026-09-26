import sqlite3

conn = sqlite3.connect(r'F:\D\20-火枭\输出数据\huoxiao_cache.db')
cursor = conn.cursor()

# 创建节点池表
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

# 创建索引
cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_pool_score ON node_pool(score DESC)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_pool_level ON node_pool(pool_level)')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_node_pool_audit ON node_pool(audit_status)')

conn.commit()

# 验证
cursor.execute("PRAGMA table_info(node_pool)")
print('node_pool表字段：')
for col in cursor.fetchall():
    print(f'  - {col[1]} ({col[2]})')

conn.close()
print('\n✅ 节点池表创建成功！')
