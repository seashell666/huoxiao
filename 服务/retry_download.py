# -*- coding: utf-8 -*-
"""重试批量下载失败的 27 条（同无水印链路）"""
import sys, os, json, time, sqlite3, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
from huoxiao_client import GuestChannel

OUT_DIR = r'F:\D\20-火枭\视频下载\批量原画'
PROG = os.path.join(OUT_DIR, '_retry_progress.json')
LOG = os.path.join(OUT_DIR, '_retry.log')

def log(msg):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# 读上次失败清单
with open(os.path.join(OUT_DIR, '_progress.json'), encoding='utf-8') as f:
    prev = json.load(f)
fails = prev.get('fail_list', [])
log(f'待重试: {len(fails)} 条')

prog = {'start_time': time.strftime('%Y-%m-%d %H:%M:%S'), 'total': len(fails),
        'done': 0, 'success': 0, 'skipped': 0, 'fail': 0, 'fail_list': [],
        'current': '', 'last_update': ''}
with open(PROG, 'w', encoding='utf-8') as f:
    json.dump(prog, f, ensure_ascii=False, indent=1)

g = GuestChannel(min_interval=1.5)
t0 = time.time()
for i, aid in enumerate(fails):
    prog['current'] = aid; prog['done'] = i
    prog['last_update'] = time.strftime('%H:%M:%S')
    with open(PROG, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=1)

    url = None; gear = ''
    try:
        j = g.app.get_page_detail(aid)
        v = (j.get("aweme_detail") or {}).get("video") or {}
        br = v.get("bit_rate") or []
        for b in br:
            if "1440" in str(b.get("gear_name") or ""):
                ul = (b.get("play_addr") or {}).get("url_list")
                if ul: url = ul[0]; gear = str(b.get("gear_name")); break
        if not url and br:
            ul = (br[0].get("play_addr") or {}).get("url_list")
            if ul: url = ul[0]; gear = str(br[0].get("gear_name") or '')
    except Exception as e:
        log(f'{i+1}/{len(fails)} {aid} 取详情失败: {str(e)[:70]}')

    if not url:
        prog['skipped'] += 1
        log(f'{i+1}/{len(fails)} {aid} 无原画档地址(跳过)')
        with open(PROG, 'w', encoding='utf-8') as f:
            json.dump(prog, f, ensure_ascii=False, indent=1)
        time.sleep(1.0); continue

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
            log(f'{i+1}/{len(fails)} {aid} 下载第{attempt+1}次失败: {str(e)[:70]}')
            time.sleep(2)

    if ok:
        prog['success'] += 1
        log(f'{i+1}/{len(fails)} {aid} {gear} {len(data)/1024/1024:.1f}MB OK')
    else:
        prog['fail'] += 1; prog['fail_list'].append(aid)
        log(f'{i+1}/{len(fails)} {aid} 最终失败')
    with open(PROG, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=1)
    time.sleep(1.0)

prog['done'] = len(fails); prog['current'] = '完成'
prog['last_update'] = time.strftime('%H:%M:%S')
with open(PROG, 'w', encoding='utf-8') as f:
    json.dump(prog, f, ensure_ascii=False, indent=1)
log(f'=== 重试结束: 成功{prog["success"]} 跳过{prog["skipped"]} 失败{prog["fail"]} ===')
