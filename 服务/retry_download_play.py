# -*- coding: utf-8 -*-
"""兜底下载：389 条里未成功落盘的（74跳过+25失败=99条）全部改用「游客通道 play_addr(原样)」
产物放独立子目录，与无水印原画档分开"""
import sys, os, json, time, sqlite3, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
from huoxiao_client import GuestChannel

DB = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
BASE = r'F:\D\20-火枭\视频下载\批量原画'
OUT_DIR = os.path.join(BASE, '游客play兜底')
os.makedirs(OUT_DIR, exist_ok=True)
LOG = os.path.join(BASE, '_retry_play.log')

def log(msg):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# 1) 全部 389 条待下载 aid（深采且有 play_url）
conn = sqlite3.connect(DB); conn.text_factory = str
cur = conn.cursor()
cur.execute("SELECT aweme_id, payload_json FROM video_cache")
all_aids = []
for aid, payload in cur.fetchall():
    try:
        d = json.loads(payload)
    except Exception:
        continue
    if 'music' in d and d.get('play_url'):
        all_aids.append(aid)
conn.close()
log(f'全部深采: {len(all_aids)} 条')

# 2) 原画档目录里已有文件的 = 已成功，跳过
todo = []
for aid in all_aids:
    fp = os.path.join(BASE, f'{aid}.mp4')
    if os.path.exists(fp) and os.path.getsize(fp) > 100 * 1024:
        continue
    todo.append(aid)
log(f'未落盘需兜底: {len(todo)} 条')

prog = {'start_time': time.strftime('%Y-%m-%d %H:%M:%S'), 'total': len(todo),
        'done': 0, 'success': 0, 'fail': 0, 'fail_list': [],
        'current': '', 'last_update': ''}
with open(os.path.join(BASE, '_retry_play_progress.json'), 'w', encoding='utf-8') as f:
    json.dump(prog, f, ensure_ascii=False, indent=1)

g = GuestChannel(min_interval=1.5)
for i, aid in enumerate(todo):
    prog['current'] = aid; prog['done'] = i
    prog['last_update'] = time.strftime('%H:%M:%S')
    with open(os.path.join(BASE, '_retry_play_progress.json'), 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=1)

    url = None
    try:
        j = g.app.get_page_detail(aid)
        v = (j.get("aweme_detail") or {}).get("video") or {}
        ul = (v.get("play_addr") or {}).get("url_list")
        if ul:
            url = ul[0]
    except Exception as e:
        log(f'{i+1}/{len(todo)} {aid} 取详情失败: {str(e)[:70]}')

    if not url:
        prog['fail'] += 1; prog['fail_list'].append(aid)
        log(f'{i+1}/{len(todo)} {aid} 无play地址')
        with open(os.path.join(BASE, '_retry_play_progress.json'), 'w', encoding='utf-8') as f:
            json.dump(prog, f, ensure_ascii=False, indent=1)
        time.sleep(1.0); continue

    done = False
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.douyin.com/'})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < 100 * 1024:
                raise ValueError(f'文件过小 {len(data)}B')
            with open(os.path.join(OUT_DIR, f'{aid}.mp4'), 'wb') as f:
                f.write(data)
            done = True
            break
        except Exception as e:
            log(f'{i+1}/{len(todo)} {aid} 第{attempt+1}次失败: {str(e)[:70]}')
            time.sleep(2)

    if done:
        prog['success'] += 1
        log(f'{i+1}/{len(todo)} {aid} {len(data)/1024/1024:.1f}MB OK (游客play)')
    else:
        prog['fail'] += 1; prog['fail_list'].append(aid)
        log(f'{i+1}/{len(todo)} {aid} 兜底也失败')
    with open(os.path.join(BASE, '_retry_play_progress.json'), 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=1)
    time.sleep(1.0)

prog['done'] = len(todo); prog['current'] = '完成'
prog['last_update'] = time.strftime('%H:%M:%S')
with open(os.path.join(BASE, '_retry_play_progress.json'), 'w', encoding='utf-8') as f:
    json.dump(prog, f, ensure_ascii=False, indent=1)
log(f'=== 兜底结束: 成功{prog["success"]} 失败{prog["fail"]} ===')
