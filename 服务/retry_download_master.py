# -*- coding: utf-8 -*-
"""终极兜底：15 条彻底失败改用「主号通道 bit_rate 原画档」下载
产物放独立子目录，可能带水印"""
import sys, os, json, time, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"F:\D\20-火枭\服务")
os.chdir(r"F:\D\20-火枭\参考-DouYin_Spider")
from huoxiao_client import AuthChannel, load_vault_cookie

BASE = r'F:\D\20-火枭\视频下载\批量原画'
OUT_DIR = os.path.join(BASE, '主号bitrate兜底')
os.makedirs(OUT_DIR, exist_ok=True)
LOG = os.path.join(BASE, '_retry_master_bitrate.log')

def log(msg):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# 读最终失败 15 条
with open(os.path.join(BASE, '_retry_play_progress.json'), encoding='utf-8') as f:
    rp = json.load(f)
fails = rp.get('fail_list', [])
log(f'主号原画兜底尝试: {len(fails)} 条')

ck = load_vault_cookie()
if not ck:
    log('无主号 cookie，无法继续'); sys.exit(1)
auth = AuthChannel(ck, min_interval=5.0)

ok = 0; no = 0
for i, aid in enumerate(fails):
    url = None; gear = ''
    try:
        j = auth.web_get("/aweme/v1/web/aweme/detail/", {"aweme_id": aid},
                         f"https://www.douyin.com/video/{aid}")
        v = (j.get("aweme_detail") or {}).get("video") or {}
        br = v.get("bit_rate") or []
        for b in br:
            if "1080" in str(b.get("gear_name") or ""):
                ul = (b.get("play_addr") or {}).get("url_list")
                if ul: url = ul[0]; gear = str(b.get("gear_name")); break
        if not url and br:
            ul = (br[0].get("play_addr") or {}).get("url_list")
            if ul: url = ul[0]; gear = str(br[0].get("gear_name") or '')
    except Exception as e:
        log(f'{i+1}/{len(fails)} {aid} 取详情失败: {str(e)[:70]}')

    if not url:
        no += 1
        log(f'{i+1}/{len(fails)} {aid} 主号无原画档地址')
        time.sleep(5.0); continue

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
            log(f'{i+1}/{len(fails)} {aid} 第{attempt+1}次失败: {str(e)[:70]}')
            time.sleep(2)

    if done:
        ok += 1
        log(f'{i+1}/{len(fails)} {aid} {gear} {len(data)/1024/1024:.1f}MB OK (主号原画)')
    else:
        no += 1
        log(f'{i+1}/{len(fails)} {aid} 主号也失败')
    time.sleep(5.0)

log(f'=== 主号兜底结束: 成功{ok} 失败{no} ===')
