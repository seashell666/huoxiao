import sqlite3
import time

DB_PATH = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'

# 节点池配置
MAX_NODES = 1000  # 最多1000个节点
HIGH_POOL_SIZE = 200  # 高权重池200个
PROTECT_DAYS = 7  # 新手保护期7天

class NodePool:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def add_node(self, sec_uid, nickname=''):
        """添加新节点"""
        now = int(time.time())
        protect_until = now + PROTECT_DAYS * 24 * 3600

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO node_pool 
            (sec_uid, nickname, score, pool_level, audit_status, created_at, protect_until, last_updated)
            VALUES (?, ?, 0.001, 'low', 'pending', ?, ?, ?)
        ''', (sec_uid, nickname, now, protect_until, now))
        self.conn.commit()

        print(f'✅ 添加新节点：{nickname} ({sec_uid[:20]}...)')
        return cursor.rowcount > 0

    def update_score(self, sec_uid, delta):
        """更新节点分数"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE node_pool 
            SET score = score + ?, last_updated = ?
            WHERE sec_uid = ?
        ''', (delta, int(time.time()), sec_uid))
        self.conn.commit()

        # 检查是否需要升级到高权重池
        self._check_upgrade(sec_uid)

    def _check_upgrade(self, sec_uid):
        """检查是否需要升级到高权重池"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT score, pool_level, audit_status FROM node_pool WHERE sec_uid = ?', (sec_uid,))
        row = cursor.fetchone()

        if not row:
            return

        score = row['score']
        pool_level = row['pool_level']
        audit_status = row['audit_status']

        # 6分以上，待审核
        if score >= 6 and pool_level == 'low' and audit_status == 'pending':
            print(f'🔔 节点 {sec_uid[:20]}... 分数 {score}，待审核进入高权重池')

    def get_next_task(self):
        """获取下一个要采集的节点"""
        cursor = self.conn.cursor()

        # 优先高权重池，按分数降序
        cursor.execute('''
            SELECT * FROM node_pool 
            WHERE pool_level = 'high' AND audit_status = 'approved'
            ORDER BY score DESC, last_updated ASC
            LIMIT 1
        ''')
        node = cursor.fetchone()

        if not node:
            # 然后低权重池，按分数降序
            cursor.execute('''
                SELECT * FROM node_pool 
                WHERE pool_level = 'low'
                ORDER BY score DESC, last_updated ASC
                LIMIT 1
            ''')
            node = cursor.fetchone()

        return dict(node) if node else None

    def get_stats(self):
        """获取节点池统计"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) as total FROM node_pool')
        total = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as high FROM node_pool WHERE pool_level = 'high'")
        high = cursor.fetchone()['high']

        cursor.execute("SELECT COUNT(*) as pending FROM node_pool WHERE audit_status = 'pending'")
        pending = cursor.fetchone()['pending']

        return {
            'total': total,
            'high_pool': high,
            'low_pool': total - high,
            'pending_audit': pending,
            'max': MAX_NODES
        }

    def close(self):
        self.conn.close()


# 测试
if __name__ == '__main__':
    pool = NodePool()
    stats = pool.get_stats()
    print('节点池统计：')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    pool.close()
