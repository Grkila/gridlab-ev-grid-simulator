"""Isolated real HTTP/JSONL fixture; never launches Codex or a simulation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

if '--cli' in sys.argv:
    prompt=sys.stdin.read()
    user=prompt.rsplit('USER: ',1)[-1]
    print(json.dumps(dict(type='item.completed',item=dict(id='tool-0',type='mcp_tool_call',tool='ev_get_results',server='ev_playground',status='completed',result=dict(run_id='run-fixture',payload='z'*50000)))),flush=True)
    if user.startswith('slow'):
        time.sleep(60)
    print(json.dumps(dict(type='item.completed',item=dict(id='message-0',type='agent_message',text='Fixture answer: '+user))),flush=True)
else:
    from mvgrid.novi_sad.playground_app import chat
    from mvgrid.novi_sad.playground_app.server import create_server
    original=subprocess.Popen
    def fake(args,**kwargs):
        if args[0]=='test-fake-codex': args=[sys.executable,str(Path(__file__).resolve()),'--cli']
        return original(args,**kwargs)
    subprocess.Popen=fake
    chat.codex_executable=lambda:'test-fake-codex'
    with tempfile.TemporaryDirectory(prefix='ev-chat-browser-') as root:
        server=create_server(0,root)
        print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}'}),flush=True)
        try: server.serve_forever()
        finally: server.server_close()
