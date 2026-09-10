"""Offline regressions for recovery, readiness, transport and evidence retention."""
import io
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from mvgrid.novi_sad.playground.service import Service, read_json, write_json
from mvgrid.novi_sad.playground_app.chat import ChatService


class ChatRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.chat=ChatService(Service(self.tmp.name))
        for name in ('codex_executable','threading.Thread','threading.Timer'):
            p=patch('mvgrid.novi_sad.playground_app.chat.'+name)
            result=p.start(); self.addCleanup(p.stop)
            if name=='codex_executable': result.return_value='codex.exe'

    def start(self,text='repeat',request='request-test',**kwargs):
        return self.chat.start(text,request_id=request,**kwargs)

    def execute(self,record):
        process=Mock();process.stdin=io.StringIO();process.stderr=io.StringIO('')
        process.stdout=io.StringIO(json.dumps(dict(type='item.completed',item=dict(type='agent_message',id='0',text='Answer')))+'\n')
        process.wait.return_value=0;process.poll.return_value=0
        # Cleanup must finish before any terminal-ready snapshot becomes observable.
        original_close=process.stdout.close
        observed=[]
        def close():
            observed.append(self.chat.snapshot(record['chat_id']))
            original_close()
        process.stdout.close=close
        with patch('mvgrid.novi_sad.playground_app.chat.subprocess.Popen',return_value=process):
            self.chat._run(record['chat_id'],'codex.exe')
        self.assertTrue(all(r['status']=='running' and not r['can_send'] for r in observed))
        self.assertTrue(self.chat.snapshot(record['chat_id'])['can_send'])

    def test_lost_response_is_idempotent_before_and_after_completion(self):
        first=self.start()
        self.assertEqual(self.start()['chat_id'],first['chat_id'])
        self.assertEqual(len(self.chat.get(first['chat_id'])['messages']),1)
        with self.assertRaises(ValueError): self.start('different')
        self.execute(first)
        self.assertEqual(self.start()['chat_id'],first['chat_id'])
        self.assertEqual(len(self.chat.get(first['chat_id'])['messages']),2)

    def test_active_recovery_restart_and_instance_scope(self):
        record=self.start(); current=self.chat.current()
        self.assertEqual(current['active_chat_id'],record['chat_id']);self.assertFalse(current['can_send'])
        restarted=ChatService(self.chat.service)
        self.assertEqual(restarted.instance_id,self.chat.instance_id)
        self.assertEqual(restarted.snapshot(record['chat_id'])['status'],'interrupted')
        self.assertNotEqual(ChatService(Service(self.tmp.name+'/other')).instance_id,self.chat.instance_id)

    def test_cancel_keeps_gate_closed_until_cleanup(self):
        record=self.start(); self.chat.cancel(record['chat_id'])
        self.assertFalse(self.chat.snapshot(record['chat_id'])['can_send'])
        with self.assertRaises(ValueError): self.start(request='request-second')
        self.execute(record)
        self.assertEqual(self.chat.get(record['chat_id'])['status'],'cancelled')

    def test_sequences_do_not_collapse_identical_turns_and_delta_is_empty(self):
        record=self.start();self.execute(record)
        second=self.start(request='request-second',chat_id=record['chat_id']);self.execute(second)
        snapshot=self.chat.snapshot(record['chat_id'])
        self.assertEqual([m['content'] for m in snapshot['messages'] if m['role']=='user'],['repeat','repeat'])
        self.assertEqual(len({m['turn_id'] for m in snapshot['messages']}),2)
        self.assertEqual(len({m['event_id'] for m in snapshot['messages']}),4)
        delta=self.chat.snapshot(record['chat_id'],snapshot['cursor'])
        self.assertEqual(delta['events'],[]);self.assertEqual(delta['messages'],[])

    def test_large_evidence_is_exact_and_retention_gap_resets(self):
        r=self.start()
        event=dict(type='item.completed',item=dict(id='0',type='mcp_tool_call',tool='ev_get_results',result={'run_id':'run-test','payload':'x'*100000}))
        self.chat._event(r,event)
        output_id=r['events'][-1]['full_url'].split('/')[-1]
        self.assertEqual(self.chat.output(r['chat_id'],output_id),event)
        first=r['events'][0]['seq']
        for i in range(510): self.chat._event(r,dict(type='item.started',item={'id':str(i),'text':'a'*600}))
        write_json(self.chat.path(r['chat_id']),r)
        self.assertLessEqual(len(json.dumps(r['events']).encode()),self.chat.EVENTS_BYTES)
        self.assertTrue(self.chat.snapshot(r['chat_id'],first)['reset'])
        self.assertIn('run-test',self.chat.context(r))
        self.assertEqual(self.chat.output(r['chat_id'],output_id),event)
        with self.assertRaises(ValueError): self.chat.output(r['chat_id'],'../escape')

    def test_bounded_context_preserves_exact_pinned_constraints(self):
        r=self.start(constraints='Never increase the 100 kW limit.')
        r['references']=['run-only-in-tool']
        for i in range(40): self.chat._append(r,'messages',{'role':'user','content':str(i)+'x'*3000})
        context=self.chat.context(r)
        self.assertLess(len(context),42000)
        self.assertIn('Never increase the 100 kW limit.',context)
        self.assertIn('run-only-in-tool',context)
        self.assertIn('Earlier messages omitted:',context)
        self.assertNotIn('USER: 0xxx',context)

    def test_history_pages_and_large_message_references(self):
        r=self.start('z'*19000)
        for i in range(120): self.chat._append(r,'messages',{'role':'user','content':str(i)})
        write_json(self.chat.path(r['chat_id']),r)
        latest=self.chat.snapshot(r['chat_id']);self.assertEqual(len(latest['messages']),100)
        stale=self.chat.snapshot(r['chat_id'],0)
        self.assertTrue(stale['reset']);self.assertEqual(len(stale['messages']),100)
        older=self.chat.history(r['chat_id'],latest['history_before'])
        self.assertEqual(len(older['messages']),21)
        self.assertIn('full_url',older['messages'][0])
        self.assertIsNone(older['history_before'])

    def test_thread_start_failure_releases_gate(self):
        with patch('mvgrid.novi_sad.playground_app.chat.threading.Thread') as thread:
            thread.return_value.start.side_effect=RuntimeError('failed')
            with self.assertRaises(RuntimeError): self.start()
        self.assertFalse(self.chat.active)
        self.assertEqual(self.chat.current()['chats'][0]['status'],'failed')

    def test_legacy_migration_is_stable(self):
        write_json(self.chat.path('chat-old'),dict(chat_id='chat-old',status='completed',messages=[{'role':'user','content':'same'},{'role':'user','content':'same'}],events=[]))
        first=self.chat.snapshot('chat-old');second=self.chat.snapshot('chat-old')
        self.assertEqual(first['messages'],second['messages'])
        self.assertNotEqual(first['messages'][0]['event_id'],first['messages'][1]['event_id'])
