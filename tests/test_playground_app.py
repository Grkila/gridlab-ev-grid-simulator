"""Loopback API integration and free, mocked Codex JSONL lifecycle tests."""
import http.client
import io
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from mvgrid.novi_sad.playground_app.server import create_server
from mvgrid.novi_sad.playground_app.chat import ChatService
from mvgrid.novi_sad.playground.service import Service, write_json


class AppApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=create_server(0,self.tmp.name)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.port=self.server.server_port
        self.pids=[]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        import psutil
        for pid in self.pids:
            try: psutil.Process(pid).wait(timeout=10)
            except psutil.NoSuchProcess: pass
        self.tmp.cleanup()

    def request(self,path,body=None,headers=None,raw=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=30)
        method='GET' if body is None and raw is None else 'POST'
        data=raw if raw is not None else json.dumps(body) if body is not None else None
        head={'Content-Type':'application/json',**(headers or {})}
        conn.request(method,path,data,head)
        response=conn.getresponse(); result=(response.status,json.loads(response.read()))
        conn.close();return result

    def test_host_origin_and_input_rejection(self):
        self.assertEqual(self.request('/api/catalog',headers={'Host':'attacker.example'})[0],403)
        self.assertEqual(self.request('/api/validate',{},headers={'Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.request('/api/validate',{},headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('/api/validate',raw='[')[0],400)
        self.assertEqual(self.request('/api/validate',raw='[]')[0],400)
        self.assertEqual(self.request('/api/validate',{'definition':{'unknown':True}})[0],400)
        self.assertEqual(self.request('/api/unknown')[0],404)

    def test_run_rename_delete_restore_preserves_evidence(self):
        service = Service(self.tmp.name)
        folder = service._path('runs', 'run-management-test')
        state = {'run_id':'run-management-test','status':'completed','experiment_id':'exp-test'}
        write_json(folder/'state.json', state)
        write_json(folder/'manifest.json', {'frozen':'evidence'})
        original = (folder/'manifest.json').read_bytes()
        base = '/api/runs/run-management-test'
        self.assertEqual(self.request(base+'/rename', {'name':'  Summer baseline  '})[0], 200)
        self.assertEqual(self.request(base)[1]['name'], 'Summer baseline')
        self.assertEqual(self.request(base+'/rename', {'name':'   '})[0], 400)
        self.assertEqual(self.request(base+'/rename', {'name':'x'*121})[0], 400)
        self.assertEqual(self.request(base+'/delete', {})[0], 200)
        self.assertEqual(self.request('/api/runs')[1], [])
        self.assertEqual(self.request(base+'/results')[0], 404)
        self.assertEqual(self.request(base+'/restore', {})[1]['name'], 'Summer baseline')
        self.assertEqual(len(self.request('/api/runs')[1]), 1)
        self.assertEqual((folder/'manifest.json').read_bytes(), original)
        self.assertEqual(json.loads((folder/'state.json').read_text()), state)
        write_json(folder/'state.json', {**state, 'status':'running', 'pid':os.getpid()})
        self.assertEqual(self.request(base+'/delete', {})[0], 400)
        self.assertEqual(self.request('/api/runs/run-missing/delete', {})[0], 404)

    def test_real_run_default_stop_and_network(self):
        code,network=self.request('/api/network')
        self.assertEqual(code,200)
        self.assertEqual(len(network['blocks']),52)
        self.assertFalse({'NS1','NS6','FUT'} & {b['source_id'] for b in network['blocks']})
        definition={'name':'HTTP stop acceptance','hypothesis':'Stops remain incomplete','strategies':['immediate'],'fleet':{'fleet_size':0},'limits':{'max_loading_percent':1}}
        code,valid=self.request('/api/validate',{'definition':definition},headers={'Origin':f'http://127.0.0.1:{self.port}'})
        self.assertEqual(code,200,valid)
        code,saved=self.request('/api/experiments',{'definition':definition})
        self.assertEqual(code,200,saved)
        bad,_=self.request('/api/runs',{'experiment_id':saved['experiment_id'],'runtime_root':self.tmp.name+'/wrong'})
        self.assertEqual(bad,400)
        code,job=self.request('/api/runs',{'experiment_id':saved['experiment_id'],'runtime_root':self.tmp.name})
        self.assertEqual(code,200,job)
        deadline=time.monotonic()+120
        while True:
            code,state=self.request('/api/runs/'+job['run_id'])
            self.assertEqual(code,200,state)
            if state['status'] not in ('running','starting'):break
            self.assertLess(time.monotonic(),deadline);time.sleep(.1)
        self.pids.append(state['pid'])
        self.assertEqual(state['status'],'stopped_on_violation',state)
        self.assertEqual(state['verdict'],'incomplete')
        self.assertTrue(state['warning'])
        code,result=self.request('/api/runs/'+job['run_id']+'/results')
        self.assertEqual(code,200,result)
        self.assertEqual(len(result['cases'][0]['intervals']),1)
        self.assertFalse(result['evaluation']['complete'])


class ChatJsonlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.chat=ChatService(Service(self.tmp.name))

    def record(self,name='chat-test'):
        write_json(self.chat.path(name),{'chat_id':name,'messages':[{'role':'user','content':'test'}],'events':[],'status':'running','cancel_requested':False})
        self.chat.active.add(name)
        return name

    def test_jsonl_answer_reasoning_filter_and_command_isolation(self):
        chat_id=self.record()
        process=Mock()
        self.chat.broker_url='http://127.0.0.1:8517'
        process.stdin=io.StringIO();process.stderr=io.StringIO('')
        process.stdout=io.StringIO(json.dumps({'type':'item.completed','item':{'type':'reasoning','text':'private'}})+'\nnot json\n'+json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'Evidence answer'}})+'\n')
        process.wait.return_value=0
        with patch('mvgrid.novi_sad.playground_app.chat.subprocess.Popen',return_value=process) as popen:
            self.chat._run(chat_id,'codex.exe')
        record=self.chat.get(chat_id)
        self.assertEqual(record['status'],'completed')
        self.assertEqual(record['messages'][-1]['content'],'Evidence answer')
        self.assertNotIn('private',json.dumps(record['events']))
        args=popen.call_args.args[0]
        self.assertIn('--ignore-user-config',args)
        self.assertIn('read-only',args)
        self.assertIn('mcp_servers.ev_playground.env.EV_PLAYGROUND_HOME='+json.dumps(str(self.chat.service.root)),args)
        self.assertIn('mcp_servers.ev_playground.env.EV_PLAYGROUND_BROKER_URL='+json.dumps(self.chat.broker_url),args)
        self.assertTrue(process.stdout.closed)
        self.assertFalse(self.chat.active)

    def test_failure_and_cancel_isolation(self):
        first=self.record('chat-first');second=self.record('chat-second')
        first_process=Mock();first_process.poll.return_value=None
        second_process=Mock();self.chat.processes.update({first:first_process,second:second_process})
        self.chat.cancel(first)
        first_process.terminate.assert_called_once();second_process.terminate.assert_not_called()
        self.assertTrue(self.chat.get(first)['cancel_requested'])
        self.assertFalse(self.chat.get(second)['cancel_requested'])
        with patch('mvgrid.novi_sad.playground_app.chat.subprocess.Popen',side_effect=OSError('mock startup failure')):
            self.chat._run(second,'codex.exe')
        self.assertEqual(self.chat.get(second)['status'],'failed')
        self.assertIn('mock startup failure',self.chat.get(second)['error'])

    def test_restart_and_invalid_message(self):
        chat_id=self.record();self.chat.active.clear()
        self.assertEqual(self.chat.get(chat_id)['status'],'interrupted')
        for message in ('', ' '*10, 'x'*20001, None):
            with self.assertRaises(ValueError):self.chat.start(message)
        with self.assertRaises(ValueError):self.chat.get('../outside')

    def test_loopback_broker_forwarding(self):
        service=self.chat.service
        for url in ('https://attacker.example','http://attacker.example','file:///tmp/a'):
            with patch.dict(os.environ,EV_PLAYGROUND_BROKER_URL=url):
                with self.assertRaises(ValueError):service.start_run('exp-test')
        response=io.StringIO('{"run_id":"run-broker","status":"starting"}')
        with patch.dict(os.environ,EV_PLAYGROUND_BROKER_URL='http://127.0.0.1:8517'), patch('urllib.request.urlopen',return_value=response) as open_url:
            result=service.start_run('exp-test','run-resume')
        self.assertEqual(result['run_id'],'run-broker')
        request=open_url.call_args.args[0]
        self.assertEqual(request.full_url,'http://127.0.0.1:8517/api/runs')
        payload=json.loads(request.data)
        self.assertEqual(payload,{'experiment_id':'exp-test','resume_run_id':'run-resume','runtime_root':str(service.root)})


if __name__=='__main__':unittest.main()
