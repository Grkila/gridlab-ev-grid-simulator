import tempfile, unittest
from pathlib import Path
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.schema import Experiment
from mvgrid.novi_sad.playground.strategy_workflow import StrategyWorkflow, parse_command

class WorkflowIndependentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.service=Service(self.tmp.name); self.w=StrategyWorkflow(self.service)
    def test_immutable_and_build_honesty(self):
        p=self.w.command(dict(command='PROPOSE',name='my_policy',idea='An idea'))
        s=self.w.command(dict(command='SPECIFY',based_on=p['record_id'],objective='Meet demand',information=['current sessions'],constraints=['charger bound'],algorithm='LLF',fallback='zero',research='new_hypothesis'))
        b=self.w.command(dict(command='BUILD',based_on=s['record_id']))
        self.assertEqual(b['status'],'implementation_required'); self.assertFalse(b['registered_name']); self.assertNotIn('tests_passed',b)
        self.assertNotIn('algorithm',self.w.get(p['record_id'])['spec'])
        self.assertEqual(self.w.command(dict(command='BUILD',based_on=s['record_id']))['record_id'],b['record_id'])
    def test_research_requires_reference(self):
        p=self.w.command(dict(command='PROPOSE',name='x',idea='Idea',objective='yes',information=['now'],constraints=['none'],algorithm='sort',fallback='zero',research='adaptation'))
        with self.assertRaises(ValueError): self.w.command(dict(command='SPECIFY',based_on=p['record_id']))
    def test_yaml_no_code(self):
        with self.assertRaises(Exception): parse_command('STRATEGY PROPOSE\n!!python/object/apply:os.system [echo should_not_run]')
    def test_paths_and_unknown(self):
        with self.assertRaises(ValueError): self.w.get('../../x')
        with self.assertRaises((ValueError,FileNotFoundError)): self.w.command(dict(command='BUILD',based_on='strategy-'+'a'*20,name='x'))
    def test_prepare_bounded_comparison(self):
        e=self.service.save_experiment(Experiment(name='fixture',hypothesis='fixture').model_dump(mode='json'))
        r=self.w.command(dict(command='COMPARE',scenario=e['experiment_id'],candidates=['immediate','capacity_aware'],max_cases=20))
        self.assertEqual(r['status'],'experiments_prepared')
        self.assertEqual(self.service.list_runs(),[])
        self.assertFalse(r['experiments'][0]['definition']['stop_on_violation'])

if __name__=='__main__': unittest.main()

