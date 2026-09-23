"""Manual browser fixture: real data, WebGL unavailable. No production changes.
Run from finanse: python scripts/fallback-server.py
Then open http://127.0.0.1:8766/graph and verify automatic 2D fallback.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from serve import Handler, ThreadingHTTPServer, ROOT
from urllib.parse import urlsplit

class NoWebGL(Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/graph':
            html=(ROOT/'graph.html').read_text(encoding='utf-8')
            fixture="""<script>const originalContext=HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext=function(type,...args){
if(type==='webgl'||type==='webgl2'||type==='experimental-webgl')return null;
return originalContext.call(this,type,...args);};</script>"""
            payload=html.replace('<body>','<body>'+fixture).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

if __name__=='__main__':
    print('WebGL-disabled fixture: http://127.0.0.1:8766/graph',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8766),NoWebGL).serve_forever()
