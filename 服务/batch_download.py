# -*- coding: utf-8 -*-
"""批量下载视频本体（原画档无水印链路）：
游客通道 detail → bit_rate 最高档(1440优先) play_addr → 下载 mp4
- 进度实时写 _progress.json，每完成一条更新
- 已存在且>100KB 的文件跳过（断点续跑）
- 失败重试2次，仍失败记入 fail_list 继续
"""
import sys, os, json, time, sqlite3, urllib.request, traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
from huoxiao_client import GuestChannel

DB = r'F:\D\20-火枭\输出数据\huoxiao_cache.db'
OUT_DIR = r'F:\D\20-火枭\视频下载\批量原画'
PROG = os.path.join(OUT_DIR, '_progress.json')
LOG = os.path.join(OUT_DIR, '_download.log')
os.makedirs(OUT_DIR, exist_ok=True)

def log(msg):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def save_prog(p):
    with open(PROG, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, indent=1)

# 1) 取待下载列表：深采详情且有 play_url
conn = sqlite3.connect(DB); conn.text_factory = str
cur = conn.cursor()
cur.execute("SELECT aweme_id, payload_json FROM video_cache")
aids = []
for aid, payload in cur.fetchall():
    try:
        d = json.loads(payload)
    except Exception:
        continue
    if 'music' in d and d.get('play_url'):
        aids.append(aid)
conn.close()
log(f'待下载总数: {len(aids)}')

# 2) 断点续跑：已存在且>100KB 的跳过
todo = []
for aid in aids:
    fp = os.path.join(OUT_DIR, f'{aid}.mp4')
    if os.path.exists(fp) and os.path.getsize(fp) > 100 * 1024:
        continue
    todo.append(aid)
log(f'跳过已下载: {len(aids)-len(todo)}，本次执行: {len(todo)}')

prog = {
    'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
    'total': len(todo), 'done': 0, 'success': 0, 'skipped': 0,
    'fail': 0, 'fail_list': [], 'current': '', 'last_update': '',
    'est_remaining_min': None,
}
save_prog(prog)

g = GuestChannel(min_interval=1.5)
t_start = time.time()

for i, aid in enumerate(todo):
    prog['current'] = aid
    prog['done'] = i
    prog['last_update'] = time.strftime('%H:%M:%S')
    prog['est_remaining_min'] = round((time.time() - t_start) / max(i, 1) * (len(todo) - i) / 60, 1)
    save_prog(prog)

    # 取原画档地址
    url = None; gear = ''
    try:
        j = g.app.get_page_detail(aid)
        v = (j.get("aweme_detail") or {}).get("video") or {}
        br = v.get("bit_rate") or []
        for b in br:
            if "1440" in str(b.get("gear_name") or ""):
                ul = (b.get("play_addr") or {}).get("url_list")
                if ul: url = ul[0]; gear = str(b.get("gear_name")); break
        if not url and br:  # 无1440取第一档
            ul = (br[0].get("play_addr") or {}).get("url_list")
            if ul: url = ul[0]; gear = str(br[0].get("gear_name") or '')
    except Exception as e:
        log(f'{i+1}/{len(todo)} {aid} 取详情失败: {str(e)[:80]}')
        prog['fail'] += 1; prog['fail_list'].append(aid)
        save_prog(prog); time.sleep(1.0); continue

    if not url:
        log(f'{i+1}/{len(todo)} {aid} 无原画档地址(跳过)')
        prog['skipped'] += 1
        save_prog(prog); time.sleep(1.0); continue

    # 下载（重试2次）
    ok = False
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.douyin.com/'})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if len(data) < 100 * 1024:
                raise ValueError(f'文件过小 {len(data)}B')
            fp = os.path.join(OUT_DIR, f'{aid}.mp4')
            with open(fp, 'wb') as f:
                f.write(data)
            ok = True
            break
        except Exception as e:
            log(f'{i+1}/{len(todo)} {aid} 下载第{attempt+1}次失败: {str(e)[:80]}')
            time.sleep(2)
    if ok:
        prog['success'] += 1
        log(f'{i+1}/{len(todo)} {aid} {gear} {len(data)/1024/1024:.1f}MB OK')
    else:
        prog['fail'] += 1; prog['fail_list'].append(aid)
        log(f'{i+1}/{len(todo)} {aid} 最终失败')
    save_prog(prog)
    time.sleep(1.0)

prog['done'] = len(todo)
prog['current'] = '完成'
prog['last_update'] = time.strftime('%H:%M:%S')
prog['est_remaining_min'] = 0
save_prog(prog)
log(f'=== 全部结束: 成功{prog["success"]} 跳过{prog["skipped"]} 失败{prog["fail"]} ===')
