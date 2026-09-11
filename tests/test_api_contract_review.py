"""Independent offline HTTP contracts; all worker entry points are stubbed."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from mvgrid.novi_sad.playground import continuous_campaign as campaign
from mvgrid.novi_sad.playground.benchmark import session_pool
from mvgrid.novi_sad.playground.service import Service, digest, write_json
from mvgrid.novi_sad.playground_app.server import create_server

BLOCKS = [
    {'id':'A-HOME','delivery_id':'A','kind':'residential','base_weight':1.},
    {'id':'A-HUB','delivery_id':'A','kind':'public_hub','base_weight':0.},
]


class FrozenProfileContractReview(unittest.TestCase):
    def test_factory_preserves_whole_day_and_legacy_benchmark_replays(self):
        for mode in ('whole_day', 'home_only', None):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)
                fixture=dict(blocks=BLOCKS, config={'district':'A'},
                    demand={'normal':[10.]*132,'worst':[11.]*132}, limits={},
                    districts={},network_capacity={})
                if mode is not None: fixture['config']['charging_profile']=mode
                (folder/'network.json').write_text('{}')
                write_json(folder/'fixtures.json',fixture)
                write_json(folder/'request.json',dict(config={},fixture_hash=digest(fixture),
                    network_hash=hashlib.sha256(b'{}').hexdigest(),horizon_steps=132,
                    anchors={'normal':{'fleet_size':1000}}))
                for family in ('normal','district','synchronized'):
                    episode=campaign.FrozenEpisodeFactory(folder,'benchmark',(family,1000))(41001)
                    expected=session_pool(BLOCKS,41001,1000,'A' if family=='district' else None,
                        family=='synchronized',mode or 'home_only')
                    self.assertEqual(episode['sessions'],expected)
                    self.assertEqual(episode['metadata']['replay_hash'],digest(expected))
                    self.assertTrue(all(s['departure_step']<=132 for s in expected))
                    if mode=='whole_day':
                        self.assertEqual({s['location_type'] for s in expected},
                            {'residential','workplace','public'})

    def test_generator_source_is_in_runtime_binding(self):
        binding=campaign.runtime_binding()
        source=Path(campaign.__file__).parent/'charging_profiles.py'
        self.assertIn('charging_profiles.py',campaign.MODEL_FILES)
        self.assertEqual(binding['source']['charging_profiles.py'],
            hashlib.sha256(source.read_bytes()).hexdigest())


class OfflineHTTPContractReview(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stubs={}
        for name in ('ChatService','RLService','ContinuousCampaignService'):
            stub=patch('mvgrid.novi_sad.playground_app.server.'+name,autospec=True)
            self.stubs[name]=stub.start().return_value
            self.addCleanup(stub.stop)
        self.server=create_server(0,self.tmp.name)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self,path,body=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            connection.request('GET' if body is None else 'POST',path,
                None if body is None else json.dumps(body),{'Content-Type':'application/json'})
            response=connection.getresponse()
            return response.status,json.loads(response.read())
        finally: connection.close()

    def test_chat_receipt_delta_history_and_cancel_transport(self):
        chat=self.stubs['ChatService']
        chat.start.return_value={'chat_id':'chat-test'}
        chat.snapshot.return_value={'chat_id':'chat-test','cursor':7,'messages':[]}
        body=dict(message='draft only',chat_id=None,request_id='receipt-test',
            constraints='Do not run workers',requested_action='auto',
            specification_id=None,contract_version=None)
        self.assertEqual(self.request('/api/chat',body)[0],200)
        chat.start.assert_called_once_with('draft only',None,'receipt-test',
            'Do not run workers','auto',None,None)
        write_json(Service(self.tmp.name)._path('chat-requests','receipt-test'),{'chat_id':'chat-test'})
        self.assertEqual(self.request('/api/chat/requests/receipt-test')[1]['cursor'],7)
        self.assertEqual(self.request('/api/chat/chat-test?after=7')[0],200)
        chat.snapshot.assert_called_with('chat-test',7)
        chat.history.return_value={'messages':[],'next_before':None}
        self.assertEqual(self.request('/api/chat/chat-test/history?before=12')[0],200)
        chat.history.assert_called_once_with('chat-test',12)
        self.assertEqual(self.request('/api/chat/chat-test/cancel',{})[0],200)
        chat.cancel.assert_called_once_with('chat-test')
        self.assertEqual(self.request('/api/chat/chat-test?after=invalid')[0],400)
        self.assertEqual(self.request('/api/chat/requests/missing')[0],404)

    def test_rl_start_and_cancel_preserve_payload_without_worker(self):
        rl=self.stubs['RLService']
        rl.start.return_value={'job_id':'rl-test','status':'starting'}
        rl.cancel.return_value={'job_id':'rl-test','cancel_requested':True}
        config={'episodes':3}
        self.assertEqual(self.request('/api/rl/train',{'experiment_id':'exp-test','config':config})[0],200)
        rl.start.assert_called_once_with('exp-test',config)
        self.assertTrue(self.request('/api/rl/jobs/rl-test/cancel',{})[1]['cancel_requested'])
        rl.cancel.assert_called_once_with('rl-test')
        rl.start.reset_mock()
        self.assertEqual(self.request('/api/rl/train',{'experiment_id':'exp-test',
            'runtime_root':self.tmp.name+'/other'})[0],400)
        rl.start.assert_not_called()

    def test_continuous_prepare_resume_results_and_errors_without_worker(self):
        service=self.stubs['ContinuousCampaignService']
        service.create.return_value={'campaign_id':'ppo-test','status':'prepared'}
        self.assertEqual(self.request('/api/continuous-rl/campaigns',
            {'benchmark_job_id':'bench-test','config':{'budget_hours':1}})[0],200)
        service.create.assert_called_once_with('bench-test',{'budget_hours':1})
        service.start.return_value={'campaign_id':'ppo-test','status':'queued'}
        self.assertEqual(self.request('/api/continuous-rl/campaigns/ppo-test/resume',{})[0],200)
        service.start.assert_called_once_with('ppo-test',resume=True)
        service.results.return_value={'campaign':{'status':'prepared'},'request':{},'report':None}
        self.assertIsNone(self.request('/api/continuous-rl/campaigns/ppo-test/results')[1]['report'])
        service.get.side_effect=FileNotFoundError('missing campaign')
        self.assertEqual(self.request('/api/continuous-rl/campaigns/missing')[0],404)
        service.create.side_effect=ValueError('invalid source')
        self.assertEqual(self.request('/api/continuous-rl/campaigns',{'benchmark_job_id':'bad'})[0],400)


if __name__=='__main__': unittest.main()
