# -*- coding: utf-8 -*-
"""导出：22个生产池节点 → 喜欢列表 aid 完整归属映射（多对多）+ 复用清单"""
import sqlite3, json, sys, os
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

DB = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
conn = sqlite3.connect(DB)
conn.text_factory = str
cur = conn.cursor()

# 生产池节点
cur.execute("SELECT sec_uid, nickname FROM node_pool WHERE pool_level='low'")
nodes = cur.fetchall()
print(f'生产池节点: {len(nodes)}')

# node_cache 里各节点 likes payload
cur.execute("SELECT sec_uid, dtype, payload_json, fetched_at FROM node_cache WHERE dtype='likes'")
node_likes = {}
for sec, dtype, payload, ts in cur.fetchall():
    try:
        node_likes[sec] = json.loads(payload)
    except Exception:
        node_likes[sec] = []

# aid → 节点列表（多对多）
aid_nodes = defaultdict(list)
node_aids = defaultdict(list)   # 节点 → aid 列表
total_likes = 0
for sec, nick in nodes:
    arr = node_likes.get(sec, [])
    aids = []
    for it in arr:
        aid = it.get('aweme_id')
        if aid:
            aids.append(aid)
            aid_nodes[aid].append({'sec_uid': sec, 'nickname': nick})
    node_aids[sec] = {'nickname': nick, 'aids': aids, 'n': len(aids)}
    total_likes += len(aids)

print('各节点喜欢数:')
for sec, info in node_aids.items():
    print(f'  {info["nickname"][:12]:14s} {info["n"]:3d} 条')

print(f'\n喜欢列表总计(含重复): {total_likes}')
print(f'去重视频数: {len(aid_nodes)}')

# 多节点重合情况
multi = {aid: v for aid, v in aid_nodes.items() if len(v) > 1}
print(f'被≥2个节点喜欢的视频: {len(multi)} 条')
for aid, v in sorted(multi.items(), key=lambda x: -len(x[1]))[:15]:
    print('  ', aid, '←', '、'.join(x['nickname'][:8] for x in v))

# 落盘归属 JSON（深采输入 + 看板/策展导入的基础）
out = {
    'generated_at': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'nodes': [{'sec_uid': s, 'nickname': n, 'n_likes': node_aids[s]['n']} for s, n in nodes],
    'aid_nodes': {aid: [{'sec_uid': x['sec_uid'], 'nickname': x['nickname']} for x in v]
                  for aid, v in aid_nodes.items()},
}
path = r'F:\D\20-火枭\输出数据\node_likes_ownership.json'
with open(path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f'\n归属清单已写: {path}')

# 复用：已有下载文件 ∩ 节点喜欢列表
vid_dir = r'F:\D\20-火枭\视频下载\批量原画'
exist = set()
for root, dirs, files in os.walk(vid_dir):
    for fn in files:
        if fn.endswith('.mp4'):
            exist.add(fn[:-4])
inter = set(aid_nodes.keys()) & exist
print(f'\n已有下载文件数: {len(exist)} | 节点喜欢 ∩ 已有文件 = {len(inter)} 条（直接复用）')
print('可复用的 aid 列表:', sorted(inter))

conn.close()
