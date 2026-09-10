"""Persistent chat with real Codex CLI JSONL events and the playground MCP server."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.service import Service, read_json, write_json
from mvgrid.novi_sad.playground.strategy_workflow import StrategyWorkflow


def codex_executable() -> str:
    override=os.environ.get('EV_CODEX_EXECUTABLE')
    if override:
        path=Path(override).resolve()
        if not path.is_file() or path.suffix.lower() in ('.cmd','.bat'):
            raise ValueError('EV_CODEX_EXECUTABLE must identify a native executable.')
        return str(path)
    command=shutil.which('codex')
    if command and Path(command).suffix.lower() not in ('.cmd','.bat'):
        return command
    # Desktop installer uses a versioned native binary behind its Windows wrapper.
    base=Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI'/'Codex'/'bin'
    candidates=list(base.rglob('codex.exe')) if base.exists() else []
    if candidates: return str(max(candidates,key=lambda p:p.stat().st_mtime))
    raise FileNotFoundError('Codex CLI not found. Install/sign in to Codex, or set EV_CODEX_EXECUTABLE.')


class ChatService:
    def __init__(self, service: Service):
        self.service=service
        self.lock=threading.RLock()
        self.processes={}
        self.active=set()
        self.broker_url=None

    def path(self, chat_id):
        return self.service._path('chats',chat_id).with_suffix('.json')

    def get(self, chat_id):
        with self.lock:
            record=read_json(self.path(chat_id))
            if record['status']=='running' and chat_id not in self.active:
                record.update(status='interrupted',error='App restarted during this chat turn; send a new message to continue.')
                write_json(self.path(chat_id),record)
            return record

    def start(self,message,chat_id=None):
        if not isinstance(message,str) or not message.strip() or len(message)>20000:
            raise ValueError('Enter a message between 1 and 20,000 characters.')
        executable=codex_executable()
        with self.lock:
            if self.active: raise ValueError('A Codex response is already running. Wait or cancel it first.')
            build_request=None
            if re.match(r'^\s*STRATEGY\s+BUILD(?:\s|$)',message,re.IGNORECASE):
                build_request=StrategyWorkflow(self.service).command(message)
            chat_id=chat_id or 'chat-'+uuid.uuid4().hex[:16]
            record=self.get(chat_id) if self.path(chat_id).exists() else {'chat_id':chat_id,'messages':[],'events':[]}
            record['messages'].append({'role':'user','content':message.strip()})
            record.update(status='running',error=None,started_at=time.time(),cancel_requested=False,
                          mode='strategy_build' if build_request else 'experiment',build_request=build_request)
            write_json(self.path(chat_id),record)
            self.active.add(chat_id)
            threading.Thread(target=self._run,args=(chat_id,executable),daemon=True).start()
            return record

    def cancel(self,chat_id):
        with self.lock:
            record=self.get(chat_id)
            if chat_id in self.active:
                record['cancel_requested']=True
                write_json(self.path(chat_id),record)
                process=self.processes.get(chat_id)
                if process and process.poll() is None: process.terminate()
            return record

    def _run(self,chat_id,executable):
        process = None
        deadline = None
        try:
            record=read_json(self.path(chat_id))
            build_request=record.get('build_request')
            instruction=(
                'You are the EV hypothesis playground assistant. Use the ev_playground MCP tools for all experiment operations. '
                'First discover their current catalog and strategy catalog when needed. '
                'Create, validate, save, run and explain experiments when asked; report actual tool results and immutable IDs. '
                'Read the live catalog for current network scope and capacity provenance; do not assume a remembered topology. '
                'Default stop_on_violation stops at first electrical violation; stopped prefixes are incomplete, never a successful full comparison. '
                'Never silently relax assertions or limits. Set case_origin to llm when you formulate an experiment. Explain assumptions and synthetic model limitations. '
                'Use concise plain language. If a run is still executing, give its ID so the dashboard can monitor it. '
                'Use ev_strategy_command for standardized STRATEGY PROPOSE/SPECIFY/BUILD/COMPARE/CHALLENGE/REVISE requests. '
                'Use primary research papers when proposing strategies; web search is available for research and official technical documentation. '
                'Preserve exact paper mechanisms and distinguish adaptation from reproduction. '
                'COMPARE/CHALLENGE prepare experiments; start them with ev_start_run when comparison was requested. '
                'BUILD returns a coding handoff, never proof that implementation succeeded. '
                'Do not contact unrelated services. '
            )
            if build_request:
                instruction+=(
                    'This turn is an explicit request to implement the saved strategy. Workspace editing is enabled. '
                    'Read AGENTS.md and plugins/ev-hypothesis-playground/skills/ev-experiments/SKILL.md. '
                    'Implement the specification and necessary registration/tests/docs in this repository. '
                    'Preserve unrelated work. Do not commit, push, delete runs, install unrelated software or modify personal configuration. '
                    'Run meaningful tests and required repository checks. Report actual results and remaining failures. '
                    'Do not claim the running app reloaded Python source automatically; a restart may be needed. '
                    +build_request['coding_prompt']+'\n'
                )
            else:
                instruction+='Use ev_playground tools for experiment operations. Do not edit code or run shell commands in this turn. To implement a new controller, give the user STRATEGY BUILD with a saved specified record ID. '
            instruction+='The following is this chat transcript:\n'
            transcript='\n\n'.join(m['role'].upper()+': '+m['content'] for m in record['messages'][-20:])
            args=[executable,'exec','--json','--ephemeral','--ignore-user-config','--sandbox','workspace-write' if build_request else 'read-only','--color','never',
                  '-C',str(REPOSITORY_ROOT),'-c','approval_policy="never"',
                  '-c','web_search="live"',
                  '-c','mcp_servers.ev_playground.command='+json.dumps(sys.executable),
                  '-c','mcp_servers.ev_playground.args='+json.dumps([str(REPOSITORY_ROOT/'scripts/run_playground_mcp.py')]),
                  '-c','mcp_servers.ev_playground.env.EV_PLAYGROUND_HOME='+json.dumps(str(self.service.root)),
                  '-c','mcp_servers.ev_playground.startup_timeout_sec=30',
                  '-c','mcp_servers.ev_playground.tool_timeout_sec=120','-']
            if self.broker_url:
                args[-1:-1]=["-c", "mcp_servers.ev_playground.env.EV_PLAYGROUND_BROKER_URL="+json.dumps(self.broker_url)]
            process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',errors='replace',cwd=str(REPOSITORY_ROOT),
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            with self.lock:
                self.processes[chat_id]=process
                if read_json(self.path(chat_id)).get('cancel_requested'): process.terminate()
            stderr=[]
            def drain():
                for line in process.stderr:
                    stderr.append(line)
                    if len(stderr)>100: del stderr[0]
            threading.Thread(target=drain,daemon=True).start()
            deadline=threading.Timer(1800 if build_request else 180,process.terminate)
            deadline.daemon=True
            deadline.start()
            process.stdin.write(instruction+transcript)
            process.stdin.close()
            answers=[]
            for line in process.stdout:
                try: event=json.loads(line)
                except json.JSONDecodeError: continue
                # Preserve observable messages/tool calls, never expose raw reasoning records.
                item=event.get('item',{})
                if item.get('type')=='reasoning': continue
                if event.get('type')=='item.completed' and item.get('type')=='agent_message':
                    answers.append(item.get('text',''))
                with self.lock:
                    current=read_json(self.path(chat_id))
                    current['events'].append(event)
                    current['events']=current['events'][-500:]
                    write_json(self.path(chat_id),current)
            code=process.wait()
            deadline.cancel()
            with self.lock:
                current=read_json(self.path(chat_id))
                if answers: current['messages'].append({'role':'assistant','content':'\n\n'.join(answers)})
                current['status']='cancelled' if current.get('cancel_requested') else 'completed' if code==0 else 'failed'
                if code!=0 and not current.get('cancel_requested'):
                    current['error']='Codex CLI did not complete. '+''.join(stderr)[-3000:]
                current['finished_at']=time.time()
                write_json(self.path(chat_id),current)
        except Exception as exc:
            with self.lock:
                current=read_json(self.path(chat_id))
                current.update(status='cancelled' if current.get('cancel_requested') else 'failed',error=None if current.get('cancel_requested') else str(exc))
                write_json(self.path(chat_id),current)
        finally:
            if deadline is not None: deadline.cancel()
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
                for stream in (process.stdin,process.stdout,process.stderr):
                    if stream is not None: stream.close()
            with self.lock:
                self.active.discard(chat_id)
                self.processes.pop(chat_id,None)
