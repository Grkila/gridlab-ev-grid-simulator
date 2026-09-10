"""Summary reads preserve evidence semantics without parsing detailed snapshots."""
import tempfile
import unittest
from unittest.mock import patch
from mvgrid.novi_sad.playground.service import Service, read_json, write_json


class SummaryReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.service=Service(self.tmp.name)
        self.folder=self.service._path('runs','run-test')
        write_json(self.folder/'state.json',dict(run_id='run-test',status='completed',experiment_id='exp-test'))
        write_json(self.folder/'evaluation.json',dict(complete=False,verdict='incomplete',assertions=[{'passed':False}]))
        for i in range(3):
            case_id=f'case-{i:04d}'
            case=dict(case_id=case_id,strategy='immediate',seed=1,fleet_size=1,metrics={'peak_demand_kw':42},complete=i!=1,
                      stop_reason={'violations':['test']} if i==1 else None,intervals=[{'payload':'x'*100000}])
            write_json(self.folder/'cases'/(case_id+'.json'),case)

    def test_cached_summary_never_reads_detail_and_preserves_flags(self):
        first=self.service.get_results('run-test',summary=True)
        def guarded(path):
            if path.parent.name=='cases': raise AssertionError('Read detail for summary')
            return read_json(path)
        with patch('mvgrid.novi_sad.playground.service.read_json',side_effect=guarded):
            second=self.service.get_results('run-test',summary=True)
        self.assertEqual(first,second)
        self.assertFalse(second['cases'][1]['complete'])
        self.assertEqual(second['cases'][1]['stop_reason'],{'violations':['test']})
        self.assertFalse(second['evaluation']['complete'])

    def test_pagination_is_complete_and_evaluation_remains_whole_run(self):
        page=self.service.get_results('run-test',summary=True,limit=1);ids=[]
        while True:
            ids.extend(c['case_id'] for c in page['cases'])
            self.assertEqual(page['evaluation_scope'],'whole_run')
            self.assertEqual(page['total_cases'],3)
            self.assertFalse(page['evaluation']['complete'])
            if not page['next_cursor']: break
            page=self.service.get_results('run-test',summary=True,limit=1,after=page['next_cursor'])
        self.assertEqual(ids,['case-0000','case-0001','case-0002'])

    def test_replaced_case_invalidates_derived_summary(self):
        self.service.get_results('run-test',summary=True)
        source=self.folder/'cases'/'case-0000.json'
        changed=read_json(source);changed['metrics']['peak_demand_kw']=1234
        write_json(source,changed)
        self.assertEqual(self.service.get_results('run-test','case-0000',summary=True)['cases'][0]['metrics']['peak_demand_kw'],1234)
        self.assertIn('intervals',self.service.get_results('run-test','case-0000')['cases'][0])

    def test_list_pages_are_compact_and_skip_deleted_runs(self):
        for i in range(3):
            write_json(self.service._path('experiments',f'exp-{i}').with_suffix('.json'),dict(experiment_id=f'exp-{i}',definition={'name':str(i),'large':'x'*100000}))
        write_json(self.folder/'metadata.json',{'deleted_at':'today'})
        page=self.service.list_page(1);ids=[]
        while True:
            ids.extend(r['experiment_id'] for r in page['experiments'])
            self.assertEqual(page['runs'],[])
            self.assertTrue(all('definition' not in r for r in page['experiments']))
            if not page['next_cursor']: break
            page=self.service.list_page(1,page['next_cursor'])
        self.assertEqual(ids,['exp-0','exp-1','exp-2'])
