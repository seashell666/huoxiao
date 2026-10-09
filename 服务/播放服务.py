# -*- coding: utf-8 -*-
"""火枭视频播放服务：静态服务(节点深采目录) + /play 接口调 PotPlayer 播原画
用法: python 播放服务.py [端口]  (默认 8765)
"""
import os, re, json, subprocess, sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = r'F:\D\20-火枭\视频下载\节点深采'
AUDIO_DIR = r'F:\D\20-火枭\视频下载\音频兜底归档'
POTPLAYER = r"C:\Users\Administrator\Desktop\soft\系统工具\potplayer\PotPlayerMini64.exe"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/play':
            q = parse_qs(parsed.query)
            aid = (q.get('aid') or [''])[0]
            if not re.fullmatch(r'\d{15,20}', aid):
                self._json({'ok': False, 'error': 'aid 格式不对'})
                return
            f = os.path.join(ROOT, aid + '.mp4')
            if not os.path.exists(f):
                self._json({'ok': False, 'error': '文件不存在'})
                return
            try:
                subprocess.Popen([POTPLAYER, f])
                self._html('<meta charset="utf-8"><title>播放启动</title>'
                           '<body style="font-family:sans-serif;text-align:center;padding-top:90px;'
                           'background:#0f0f0f;color:#eee"><h2>已在 PotPlayer 中打开原画播放</h2>'
                           '<p style="color:#999">本页将自动关闭</p>'
                           '<script>setTimeout(function(){window.close();},1200);</script>')
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return
        if parsed.path == '/audio':
            q = parse_qs(parsed.query)
            aid = (q.get('aid') or [''])[0]
            if not re.fullmatch(r'\d{15,20}', aid):
                self._json({'ok': False, 'error': 'aid 格式不对'})
                return
            f = os.path.join(AUDIO_DIR, aid + '.mp4')
            if not os.path.exists(f):
                self._json({'ok': False, 'error': '音频文件不存在'})
                return
            try:
                with open(f, 'rb') as fh:
                    head = fh.read(4)
                mime = 'audio/mpeg' if head[:3] == b'ID3' else 'audio/mp4'
                size = os.path.getsize(f)
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(size))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(f, 'rb') as fh:
                    while True:
                        chunk = fh.read(65536)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except Exception:
                            break
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return
        super().do_GET()

    def _html(self, inner):
        body = ('<!doctype html><html>%s</html>' % inner).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        try:
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
        except Exception:
            pass

def _safe_out(msg):
    try:
        sys.stdout.write(msg + '\n')
        sys.stdout.flush()
    except Exception:
        pass

if __name__ == '__main__':
    _safe_out(f"火枭播放服务启动: http://127.0.0.1:{PORT}  根目录={ROOT}  PotPlayer={POTPLAYER}")
    HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
