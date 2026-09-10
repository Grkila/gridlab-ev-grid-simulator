"""Loopback-only JSON API and static React assets, backed by the shared engine."""
from __future__ import annotations
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit, unquote
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.rl_service import RLService
from mvgrid.novi_sad.playground.strategy_workflow import StrategyWorkflow
from mvgrid.novi_sad.playground.network import build_network, REDUCED_PATH
from .chat import ChatService


@lru_cache(maxsize=1)
def _network_payload(revision):
    net,blocks=build_network()
    return dict(blocks=blocks,hierarchy_nodes=net['hierarchy_nodes'],hierarchy_edges=net['hierarchy_edges'],
                excluded_hubs=net.get('excluded_hubs',[]),excluded_sources=net['excluded_sources'],retained_demand_fraction=net['retained_demand_fraction'],capacity_alignment=net.get('capacity_alignment'))


def network_payload():
    stat=REDUCED_PATH.stat()
    return _network_payload((stat.st_mtime_ns,stat.st_size))


def create_server(port=8517,root=None):
    service=Service(root)
    rl_service=RLService(service.root)
    strategies=StrategyWorkflow(service)
    chats=ChatService(service)
    static=(REPOSITORY_ROOT/'web'/'dist').resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass

        def respond(self,data,status=200):
            body=json.dumps(data,allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            host=self.headers.get('Host','').split(':')[0].lower()
            return host in ('127.0.0.1','localhost')

        def do_GET(self):
            if not self.valid_host(): return self.respond({'error':'Localhost requests only'},403)
            path=unquote(urlsplit(self.path).path)
            parts=path.strip('/').split('/')
            try:
                if path=='/api/catalog': return self.respond(service.catalog())
                if path=='/api/strategies': return self.respond(strategies.catalog())
                if len(parts)==3 and parts[:2]==['api','strategies']: return self.respond(strategies.get(parts[2]))
                if path=='/api/rl/catalog': return self.respond(rl_service.catalog())
                if len(parts)==4 and parts[:3]==['api','rl','jobs']: return self.respond(rl_service.get_job(parts[3]))
                if path=='/api/network': return self.respond(network_payload())
                if path=='/api/experiments': return self.respond(service.list_experiments())
                if path=='/api/runs': return self.respond(sorted(service.list_runs(),key=lambda r:r.get('created_at',''),reverse=True))
                if len(parts)==3 and parts[:2]==['api','runs']: return self.respond(service.get_run(parts[2]))
                if len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='results': return self.respond(service.get_results(parts[2]))
                if len(parts)==3 and parts[:2]==['api','chat']: return self.respond(chats.get(parts[2]))
                if path.startswith('/api/'): return self.respond({'error':'Unknown API endpoint'},404)
                target=(static/path.lstrip('/')).resolve()
                if not target.is_relative_to(static): return self.respond({'error':'Invalid path'},400)
                if not target.is_file(): target=static/'index.html'
                if not target.is_file(): return self.respond({'error':'Build the GUI first: npm --prefix web run build'},503)
                body=target.read_bytes()
                self.send_response(200)
                content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                if target.suffix=='.js': content_type='text/javascript'
                self.send_header('Content-Type',content_type)
                self.send_header('Content-Length',str(len(body)))
                self.send_header('X-Content-Type-Options','nosniff')
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError as exc: self.respond({'error':str(exc)},404)
            except (ValueError,KeyError,TypeError) as exc: self.respond({'error':str(exc)},400)
            except Exception as exc: self.respond({'error':str(exc)},500)

        def do_POST(self):
            if not self.valid_host(): return self.respond({'error':'Localhost requests only'},403)
            origin=self.headers.get('Origin')
            if origin and (urlsplit(origin).hostname not in ('127.0.0.1','localhost') or urlsplit(origin).netloc != self.headers.get('Host')):
                return self.respond({'error':'Cross-origin requests are not allowed'},403)
            if not self.headers.get('Content-Type','').startswith('application/json'):
                return self.respond({'error':'Use application/json'},415)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 1_000_000: raise ValueError('Invalid request size')
                payload=json.loads(self.rfile.read(length))
                if not isinstance(payload,dict): raise ValueError('JSON object required')
                path=urlsplit(self.path).path
                parts=path.strip('/').split('/')
                if path=='/api/strategies/command': result=strategies.command(payload['command'])
                elif path=='/api/rl/train':
                    if payload.get('runtime_root') and Path(payload['runtime_root']).resolve()!=service.root:
                        raise ValueError('Training broker storage differs from the MCP storage.')
                    result=rl_service.start(payload['experiment_id'],payload.get('config',{}))
                elif len(parts)==5 and parts[:3]==['api','rl','jobs'] and parts[4]=='cancel': result=rl_service.cancel(parts[3])
                elif path=='/api/validate': result=service.validate_experiment(payload['definition'])
                elif path=='/api/experiments': result=service.save_experiment(payload['definition'])
                elif path=='/api/runs':
                    if payload.get('runtime_root') and Path(payload['runtime_root']).resolve()!=service.root:
                        raise ValueError('Run broker storage differs from the MCP storage.')
                    result=service.start_run(payload['experiment_id'],payload.get('resume_run_id'))
                elif path=='/api/compare': result=service.compare_runs(payload['run_ids'])
                elif path=='/api/chat': result=chats.start(payload['message'],payload.get('chat_id'))
                elif len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='rename': result=service.rename_run(parts[2],payload.get('name'))
                elif len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='delete': result=service.delete_run(parts[2])
                elif len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='restore': result=service.restore_run(parts[2])
                elif len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='cancel': result=service.cancel_run(parts[2])
                elif len(parts)==4 and parts[:2]==['api','chat'] and parts[3]=='cancel': result=chats.cancel(parts[2])
                else: return self.respond({'error':'Unknown API endpoint'},404)
                return self.respond(result)
            except FileNotFoundError as exc: self.respond({'error':str(exc)},404)
            except (ValueError,KeyError,TypeError) as exc: self.respond({'error':str(exc)},400)
            except Exception as exc: self.respond({'error':str(exc)},500)

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    chats.broker_url=f"http://127.0.0.1:{server.server_port}"
    server.chat_service=chats
    return server
