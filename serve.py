"""本地预览：python serve.py；只监听本机，不需要 npm 或联网。"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import functools

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='北京一号本地预览')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    class Handler(SimpleHTTPRequestHandler):
        extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.js':'text/javascript','.mjs':'text/javascript','.glb':'model/gltf-binary','.3mf':'model/3mf','.md':'text/plain; charset=utf-8'}
        def end_headers(self):
            self.send_header('Cache-Control','no-cache')
            super().end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(Handler,directory=str(root)))
    print(f'北京一号预览：http://127.0.0.1:{args.port}/web/\n按 Ctrl+C 停止。',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
