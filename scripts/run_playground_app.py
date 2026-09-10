"""Serve the built green GUI and local Codex CLI chat on loopback."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.novi_sad.playground_app.server import create_server

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8517)
    args=parser.parse_args()
    server=create_server(args.port)
    print(f'EV playground: http://127.0.0.1:{server.server_port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
