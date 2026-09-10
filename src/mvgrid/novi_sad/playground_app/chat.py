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
import hashlib
from .chat_records import ChatRecords
from .chat_routing import route_request
from mvgrid.novi_sad.playground.agent_contract import VERSION, check_version, render_instructions
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


class ChatService(ChatRecords):
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
            original=read_json(self.path(chat_id))
            migrate=original.get('transport_version')!=1
            record=self._normalize(original)
            if migrate: write_json(self.path(chat_id),record)
            if record['status']=='running' and chat_id not in self.active:
                record.update(status='interrupted',error='App restarted during this chat turn; send a new message to continue.')
                write_json(self.path(chat_id),record)
            return record

    def start(self,message,chat_id=None,request_id=None,constraints=None,requested_action="auto",specification_id=None,contract_version=None):
        if not isinstance(message,str) or not message.strip() or len(message)>20000:
            raise ValueError('Enter a message between 1 and 20,000 characters.')
        check_version(contract_version)
        workflow,build_command=route_request(message,requested_action,specification_id)
        if chat_id is not None:self.path(chat_id)
        with self.lock:
            if constraints is not None and (not isinstance(constraints,str) or len(constraints)>4000):
                raise ValueError('Pinned constraints must be text of at most 4,000 characters.')
            request_path=self.service._path('chat-requests',request_id) if request_id else None
            signature=hashlib.sha256(json.dumps([message,chat_id,constraints,requested_action,specification_id,contract_version]).encode()).hexdigest()
            if request_path and request_path.exists():
                previous=read_json(request_path)
                if previous['signature']!=signature: raise ValueError('Request ID already used for a different message.')
                return self.get(previous['chat_id'])
            if self.active: raise ValueError('A Codex response is already running. Wait or cancel it first.')
            executable=codex_executable()
            build_request=None
            if build_command is not None:
                if requested_action=='implement':
                    from mvgrid.novi_sad.playground.strategy_contract import AlgorithmSpecification
                    saved_spec=StrategyWorkflow(self.service).get(specification_id)['spec']
                    AlgorithmSpecification.model_validate({k:saved_spec[k] for k in AlgorithmSpecification.model_fields if k in saved_spec})
                build_request=StrategyWorkflow(self.service).command(build_command)
            chat_id=chat_id or 'chat-'+uuid.uuid4().hex[:16]
            record=self.get(chat_id) if self.path(chat_id).exists() else {'chat_id':chat_id,'messages':[],'events':[], 'sequence':0, 'transport_version':1}
            record['turn_id']='turn-'+uuid.uuid4().hex
            self._append(record,'messages',{'role':'user','content':message.strip()})
            if constraints is not None: record['constraints']=constraints
            record['references']=list(dict.fromkeys(record.get('references',[])+self.REFERENCES.findall(message)))[-80:]
            record.update(status='running',error=None,started_at=time.time(),cancel_requested=False,
                          mode='strategy_build' if build_request else 'experiment',build_request=build_request,
                          workflow=workflow,contract_version=VERSION)
            write_json(self.path(chat_id),record)
            if request_path: write_json(request_path,dict(chat_id=chat_id,signature=signature))
            self.active.add(chat_id)
            try:
                threading.Thread(target=self._run,args=(chat_id,executable),daemon=True).start()
            except Exception:
                self.active.discard(chat_id)
                record.update(status='failed',error='Unable to start chat worker.')
                write_json(self.path(chat_id),record)
                raise
            return record

    def cancel(self,chat_id):
        with self.lock:
            record=self.get(chat_id)
            if chat_id in self.active:
                record['cancel_requested']=True
                write_json(self.path(chat_id),record)
                process=self.processes.get(chat_id)
                if process and process.poll() is None: self._terminate(process)
            return record

    @staticmethod
    def _terminate(process):
        if process.poll() is not None: return
        try: process.terminate()
        except OSError: return
        def escalate():
            try:
                if process.poll() is None: process.kill()
            except OSError: pass
        timer=threading.Timer(5,escalate)
        timer.daemon=True
        timer.start()

    def _run(self,chat_id,executable):
        process = None
        deadline = None
        try:
            record=self._normalize(read_json(self.path(chat_id)))
            build_request=record.get('build_request')
            instruction=render_instructions(record.get('workflow','auto'))+'\n'
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
                instruction+='Do not edit code or run shell commands in this turn. If implementation was requested in prose, prepare the specification and guide the user to select Implement saved strategy with its ID, or send STRATEGY BUILD. Never claim implementation happened in a read-only turn. '
            instruction+='The following is this chat transcript:\n'
            transcript=self.context(record)
            args=[executable,'exec','--json','--ephemeral','--ignore-user-config','--sandbox','workspace-write' if build_request else 'read-only','--color','never',
                  '-C',str(REPOSITORY_ROOT),'-c','approval_policy="never"',
                  '-c','web_search="live"',
                  '-c','mcp_servers.ev_playground.command='+json.dumps(sys.executable),
                  '-c','mcp_servers.ev_playground.args='+json.dumps([str(REPOSITORY_ROOT/'scripts/run_playground_mcp.py')]),
                  '-c','mcp_servers.ev_playground.env.EV_PLAYGROUND_HOME='+json.dumps(str(self.service.root)),
                  '-c','mcp_servers.ev_playground.env.EV_AGENT_CONTRACT_VERSION='+json.dumps(VERSION),
                  '-c','mcp_servers.ev_playground.startup_timeout_sec=30',
                  '-c','mcp_servers.ev_playground.tool_timeout_sec=120','-']
            if self.broker_url:
                args[-1:-1]=["-c", "mcp_servers.ev_playground.env.EV_PLAYGROUND_BROKER_URL="+json.dumps(self.broker_url)]
            process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',errors='replace',cwd=str(REPOSITORY_ROOT),
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            with self.lock:
                self.processes[chat_id]=process
                if read_json(self.path(chat_id)).get('cancel_requested'): self._terminate(process)
            stderr=[]
            def drain():
                for line in process.stderr:
                    stderr.append(line)
                    if len(stderr)>100: del stderr[0]
            threading.Thread(target=drain,daemon=True).start()
            deadline=threading.Timer(1800 if build_request else 180,self._terminate,args=(process,))
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
                    current=self._normalize(read_json(self.path(chat_id)))
                    self._event(current,event)
                    write_json(self.path(chat_id),current)
            code=process.wait()
            deadline.cancel()
            with self.lock:
                current=self._normalize(read_json(self.path(chat_id)))
                if answers: self._append(current,'messages',{'role':'assistant','content':'\n\n'.join(answers)})
                current['pending_status']='cancelled' if current.get('cancel_requested') else 'completed' if code==0 else 'failed'
                if code!=0 and not current.get('cancel_requested'):
                    current['error']='Codex CLI did not complete. '+''.join(stderr)[-3000:]
                current['finished_at']=time.time()
                write_json(self.path(chat_id),current)
        except Exception as exc:
            with self.lock:
                current=self._normalize(read_json(self.path(chat_id)))
                current.update(pending_status='cancelled' if current.get('cancel_requested') else 'failed',error=None if current.get('cancel_requested') else str(exc))
                write_json(self.path(chat_id),current)
        finally:
            if deadline is not None: deadline.cancel()
            if process is not None:
                try:
                    if process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=5)
                        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
                except (OSError,subprocess.TimeoutExpired): pass
                for stream in (process.stdin,process.stdout,process.stderr):
                    try:
                        if stream is not None: stream.close()
                    except (OSError,ValueError): pass
            with self.lock:
                self.active.discard(chat_id)
                self.processes.pop(chat_id,None)
                current=self._normalize(read_json(self.path(chat_id)))
                current['status']='cancelled' if current.get('cancel_requested') else current.pop('pending_status','failed')
                current.pop('pending_status',None)
                current['finished_at']=time.time()
                write_json(self.path(chat_id),current)
