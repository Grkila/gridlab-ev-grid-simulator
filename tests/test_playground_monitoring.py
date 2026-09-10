"""Electrical monitoring, safety stop and partial-coverage regressions."""
import unittest
from mvgrid.novi_sad.playground.simulation import Simulator, simulate_case
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.worker import evaluate


class MonitoringTests(unittest.TestCase):
    def test_stop_preserves_first_counterexample_and_pending_energy(self):
        sim=Simulator()
        sim.reset({},[100000]*4,[])
        block=next(b for b in sim.blocks if b.get('kind')!='public_hub')
        session=dict(id='late',block_id=block['id'],arrival_step=2,departure_step=4,energy_kwh=10,charger_kw=7.4)
        result=simulate_case({'limits':{'max_loading_percent':1}},[100000]*4,[session])
        self.assertEqual(len(result['intervals']),1)
        self.assertFalse(result['complete'])
        self.assertEqual(result['stop_reason']['step'],0)
        self.assertEqual(result['metrics']['pending_energy_kwh'],10)
        self.assertEqual(result['metrics']['unmet_energy_kwh'],0)
        self.assertTrue(any(v['kind']=='transformer_overload' for v in result['stop_reason']['violations']))
        config=Service().validate_experiment({'name':'stop','hypothesis':'No false pass'})['definition']
        self.assertEqual(evaluate(config,[result],True)['verdict'],'incomplete')

    def test_continue_option_and_exact_hierarchy_monitoring(self):
        result=simulate_case({'stop_on_violation':False,'limits':{'max_loading_percent':1}},[100000]*2,[])
        self.assertEqual(len(result['intervals']),2)
        self.assertTrue(result['complete'])
        for interval in result['intervals']:
            self.assertAlmostEqual(sum(d['total_kw'] for d in interval['districts']),interval['total_kw'])
            self.assertEqual(len(interval['transformers']),12)
            self.assertFalse({'NS1','NS6','FUT'} & {d['source_id'] for d in interval['districts']})
            upstream=[t for t in interval['transformers'] if t['hv_kv']==110]
            self.assertEqual(len(upstream),6)
            self.assertTrue(all(t['block_ids'] for t in upstream))
            self.assertTrue(any(t['hv_kv']==35 and t['lv_kv']==10 for t in interval['transformers']))

    def test_step_api_cannot_advance_after_trip(self):
        simulator=Simulator()
        simulator.reset({'limits':{'max_loading_percent':1}},[100000]*3,[])
        observation,_,done=simulator.step()
        self.assertTrue(done)
        self.assertTrue(observation['done'])
        with self.assertRaises(RuntimeError): simulator.step()

    def test_partial_lower_bound_is_not_a_counterexample(self):
        config=Service().validate_experiment({'name':'lower bound','hypothesis':'Peak reaches threshold','assertions':[{'type':'hard','metric':'max_transformer_loading_percent','operator':'ge','value':90}]})['definition']
        result={'case_id':'prefix','complete':False,'metrics':{'max_transformer_loading_percent':60,'nonconverged_steps':0}}
        self.assertEqual(evaluate(config,[result],False)['assertions'][0]['verdict'],'incomplete')
        config['assertions'][0].update(operator='le',value=50)
        self.assertEqual(evaluate(config,[result],False)['assertions'][0]['verdict'],'failed')
