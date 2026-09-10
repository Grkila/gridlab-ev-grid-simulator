"""Independent permission-scoping and failure tests; never invoke the real Codex CLI."""
import io, json, tempfile, unittest
from unittest.mock import Mock, patch
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.strategy_workflow import StrategyWorkflow
from mvgrid.novi_sad.playground_app.chat import ChatService

class CapturedInput(io.StringIO):
    def close(self):
        if not self.closed: self.captured=self.getvalue()
        super().close()

class StrategyChatIndependentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.s=Service(self.tmp.name); self.chat=ChatService(self.s)
        self.exe=patch('mvgrid.novi_sad.playground_app.chat.codex_executable',return_value='codex.exe'); self.exe.start(); self.addCleanup(self.exe.stop)
        self.thread=patch('mvgrid.novi_sad.playground_app.chat.threading.Thread'); self.thread.start(); self.addCleanup(self.thread.stop)
        self.timer=patch('mvgrid.novi_sad.playground_app.chat.threading.Timer'); self.timer.start(); self.addCleanup(self.timer.stop)
    def spec(self):
        w=StrategyWorkflow(self.s)
        p=w.command(dict(command='PROPOSE',name='test_strategy',idea='Test urgency'))
        return w.command(dict(command='SPECIFY',based_on=p['record_id'],objective='deliver',information=['present sessions'],constraints=['charger'],algorithm='sort by slack',fallback='zero',research='new_hypothesis'))
    def execute(self,record,code=0,text='Actual result: implementation remains unfinished.'):
        process=Mock(); process.stdin=CapturedInput(); process.stdout=io.StringIO(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':text}})+'\n' if text else '')
        process.stderr=io.StringIO(''); process.wait.return_value=code; process.poll.return_value=code
        with patch('mvgrid.novi_sad.playground_app.chat.subprocess.Popen',return_value=process) as popen:
            self.chat._run(record['chat_id'],'codex.exe')
        return popen.call_args.args[0],process.stdin.captured,self.chat.get(record['chat_id'])
    def test_explicit_valid_build_grants_workspace_this_turn_only(self):
        spec=self.spec(); r=self.chat.start('STRATEGY BUILD\nbased_on: '+spec['record_id'])
        self.assertEqual(r['mode'],'strategy_build')
        args,prompt,done=self.execute(r)
        self.assertEqual(args[args.index('--sandbox')+1],'workspace-write')
        self.assertIn('sort by slack',prompt); self.assertIn('Do not commit, push',prompt)
        self.assertEqual(done['build_request']['status'],'implementation_required')
        r2=self.chat.start('Explain the results only',r['chat_id'])
        self.assertIsNone(r2['build_request']); self.assertEqual(r2['mode'],'experiment')
        args2,prompt2,done2=self.execute(r2)
        self.assertEqual(args2[args2.index('--sandbox')+1],'read-only')
        self.assertIn('Do not edit code or run shell commands in this turn',prompt2)
    def test_no_spec_or_incomplete_spec_never_starts(self):
        for message in ('STRATEGY BUILD','STRATEGY BUILD\nbased_on: strategy-'+'f'*20):
            with self.assertRaises((ValueError,FileNotFoundError)): self.chat.start(message)
        p=StrategyWorkflow(self.s).command(dict(command='PROPOSE',name='bad',idea='missing required fields'))
        with self.assertRaises(ValueError): self.chat.start('STRATEGY BUILD\nbased_on: '+p['record_id'])
        self.assertFalse(self.chat.active); self.assertFalse(list((self.s.root/'chats').glob('*.json')))
    def test_incidental_build_text_does_not_grant_write(self):
        r=self.chat.start('Explain what STRATEGY BUILD means')
        args,_,_=self.execute(r)
        self.assertEqual(args[args.index('--sandbox')+1],'read-only')
    def test_failed_cli_does_not_mark_success_or_complete_build(self):
        r=self.chat.start('STRATEGY BUILD\nbased_on: '+self.spec()['record_id'])
        _,_,done=self.execute(r,code=1,text=None)
        self.assertEqual(done['status'],'failed'); self.assertIn('did not complete',done['error'])
        self.assertEqual(done['build_request']['status'],'implementation_required')
        self.assertEqual(len(done['messages']),1)
    def test_completed_cli_preserves_actual_qualified_answer(self):
        r=self.chat.start('STRATEGY BUILD\nbased_on: '+self.spec()['record_id'])
        _,_,done=self.execute(r)
        self.assertEqual(done['messages'][-1]['content'],'Actual result: implementation remains unfinished.')
        self.assertEqual(done['build_request']['status'],'implementation_required')
        self.assertNotIn('tests_passed',done)

if __name__=='__main__': unittest.main()

