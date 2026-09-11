"""Offline HTTP and actual stdio MCP coverage for continuous campaign routing."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from mvgrid.novi_sad.playground.service import Service, write_json
from mvgrid.novi_sad.playground.continuous_campaign import ContinuousCampaignService
from mvgrid.novi_sad.playground_app.server import create_server

CAMPAIGN = 'ppo-' + 'a'*20


def fixture(root, status='prepared'):
    service = Service(root)
    folder = service._path('continuous-rl', CAMPAIGN)
    write_json(folder/'state.json', {'campaign_id':CAMPAIGN, 'status':status, 'pid':os.getpid()})
    write_json(folder/'request.json', {'config':{}, 'fixture_hash':'frozen-test'})
    return service


class ContinuousHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = fixture(self.tmp.name)
        self.server = create_server(0, self.tmp.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        connection.request('GET' if body is None else 'POST', path,
                           None if body is None else json.dumps(body), {'Content-Type':'application/json'})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_catalog_get_results_and_typed_config_rejection(self):
        code, catalog = self.request('/api/continuous-rl/catalog')
        self.assertEqual(code, 200)
        self.assertEqual(catalog['algorithm'], 'node_ppo')
        base = '/api/continuous-rl/campaigns/' + CAMPAIGN
        self.assertEqual(self.request(base)[1]['campaign_id'], CAMPAIGN)
        code, results = self.request(base+'/results')
        self.assertEqual(code, 200)
        self.assertIsNone(results['report'])
        self.assertEqual(self.request('/api/continuous-rl/campaigns', {'benchmark_job_id':'missing', 'config':{'budget_hours':-1}})[0], 400)
        self.assertEqual(self.request('/api/continuous-rl/campaigns/invalid')[0], 400)

    def test_start_resume_and_cancel_routes_preserve_intent_and_storage(self):
        base = '/api/continuous-rl/campaigns/' + CAMPAIGN
        with patch.object(ContinuousCampaignService, 'start', return_value={'campaign_id':CAMPAIGN,'status':'queued'}) as start:
            self.assertEqual(self.request(base+'/start', {})[0], 200)
            start.assert_called_once_with(CAMPAIGN, resume=False)
            start.reset_mock()
            self.assertEqual(self.request(base+'/resume', {})[0], 200)
            start.assert_called_once_with(CAMPAIGN, resume=True)
            start.reset_mock()
            self.assertEqual(self.request(base+'/start', {'runtime_root':self.tmp.name+'/different'})[0], 400)
            start.assert_not_called()
        fixture(self.tmp.name, 'running')
        self.assertTrue(self.request(base+'/cancel', {})[1]['cancel_requested'])
        self.assertTrue((self.service._path('continuous-rl', CAMPAIGN)/'cancel').exists())

    def test_shared_worker_owner_recognized_and_generic_cancel_dispatched(self):
        fixture(self.tmp.name, 'queued')
        record = self.service.get_run(CAMPAIGN)
        self.assertEqual(record['run_id'], CAMPAIGN)
        self.assertEqual(record['status'], 'starting')
        self.assertEqual(record['campaign_status'], 'queued')
        self.assertTrue(self.service.cancel_run(CAMPAIGN)['cancel_requested'])
        self.assertFalse((self.service.root/'runs'/CAMPAIGN).exists())

    def test_mcp_start_uses_app_broker_and_rejects_nonlocal_origin(self):
        from mvgrid.novi_sad.playground.mcp_server import _start_continuous_campaign
        environment = {'EV_PLAYGROUND_HOME':self.tmp.name,
                       'EV_PLAYGROUND_BROKER_URL':f'http://127.0.0.1:{self.server.server_port}'}
        with patch.dict(os.environ, environment), patch.object(ContinuousCampaignService, 'start',
                return_value={'campaign_id':CAMPAIGN,'status':'queued'}) as start:
            result = _start_continuous_campaign(CAMPAIGN, resume=True)
            self.assertEqual(result['status'], 'queued')
            start.assert_called_once_with(CAMPAIGN, resume=True)
        with patch.dict(os.environ, {'EV_PLAYGROUND_BROKER_URL':'https://example.com'}):
            with self.assertRaisesRegex(ValueError, 'loopback'):
                _start_continuous_campaign(CAMPAIGN)


class ContinuousMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_stdio_typed_discovery_and_read_cancel_roundtrip(self):
        from mcp import Client, StdioServerParameters
        from mvgrid.paths import REPOSITORY_ROOT
        with tempfile.TemporaryDirectory() as root:
            fixture(root, 'running')
            params = StdioServerParameters(command=sys.executable,
                args=[str(REPOSITORY_ROOT/'scripts/run_playground_mcp.py')],
                env={**os.environ, 'EV_PLAYGROUND_HOME':root,
                     'PYTHONPATH':str(REPOSITORY_ROOT/'src')}, cwd=tempfile.gettempdir())
            async with Client(params) as client:
                listed = await client.list_tools()
                tools = {tool.name:tool.model_dump(by_alias=True) for tool in listed.tools}
                names = ('ev_get_continuous_rl_catalog', 'ev_create_continuous_campaign',
                         'ev_start_continuous_campaign', 'ev_get_continuous_campaign',
                         'ev_get_continuous_results', 'ev_cancel_continuous_campaign',
                         'ev_resume_continuous_campaign')
                for name in names:
                    self.assertIn(name, tools)
                    self.assertIn('contract', tools[name]['outputSchema']['properties'])
                self.assertIn('budget_hours', json.dumps(tools['ev_create_continuous_campaign']['inputSchema']))
                for name, args in ((names[0], {}), (names[3], {'campaign_id':CAMPAIGN}),
                                   (names[4], {'campaign_id':CAMPAIGN}), (names[5], {'campaign_id':CAMPAIGN})):
                    result = await client.call_tool(name, args)
                    self.assertFalse(result.is_error, str(result.content))
                    self.assertIn('contract', result.structured_content)
                rejected = await client.call_tool(names[1], {'benchmark_job_id':'missing', 'config':{'budget_hours':-1}})
                self.assertTrue(rejected.is_error)


if __name__ == '__main__':
    unittest.main()
