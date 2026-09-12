"""Serve the built green GUI and local Codex CLI chat on loopback."""
import argparse
from pathlib import Path
import sys
import threading
import time
import urllib.request
import webbrowser
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.novi_sad.playground_app.server import create_server

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8517)
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--presentation', action='store_true')
    args=parser.parse_args()
    try:
        server=create_server(args.port)
    except OSError as exc:
        if getattr(exc, 'winerror', None) == 10048 or exc.errno in (48, 98, 10048):
            parser.exit(1, f'Port {args.port} is occupied. Select another port with -Port in start.ps1.\n')
        raise
    origin=f'http://127.0.0.1:{server.server_port}'
    target=origin+('/presentation.html' if args.presentation else '/')
    print(f'GridLab: {target}\nPress Ctrl+C to stop the server.',flush=True)
    def open_when_ready():
        for _ in range(40):
            try:
                with urllib.request.urlopen(origin+'/api/agent-contract',timeout=1) as response:
                    if response.status == 200:
                        if webbrowser.open(target):
                            print(f'Browser request sent: {target}',flush=True)
                        else:
                            print(f'Open this address in your browser: {target}',flush=True)
                        return
            except OSError:
                time.sleep(0.25)
        print(f'The browser did not open. Check the server and open {target}',flush=True)
    if args.open_browser:
        threading.Thread(target=open_when_ready,daemon=True).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
