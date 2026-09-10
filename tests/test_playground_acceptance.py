"""Independent acceptance checks for orchestration and unknown evidence."""
import tempfile
import time
import unittest
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.worker import evaluate


class AcceptanceTests(unittest.TestCase):
    def test_unknown_electrical_intervals_cannot_pass(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        service=Service(tmp.name)
        for metric, operator, value in [('min_voltage_pu','ge',.95),('max_line_loading_percent','le',100),('max_transformer_loading_percent','le',100),('overload_steps','le',0)]:
            config=service.validate_experiment({'name':'unknown','hypothesis':'Unknown evidence cannot pass','assertions':[dict(type='hard',metric=metric,operator=operator,value=value)]})['definition']
            result={'case_id':'x','metrics':{metric:value,'nonconverged_steps':1}}
            self.assertEqual(evaluate(config,[result],True)['verdict'],'incomplete')

    def test_stress_order_and_budget(self):
        with tempfile.TemporaryDirectory() as home:
            service=Service(home)
            def run(definition):
                exp=service.save_experiment(definition)
                job=service.start_run(exp['experiment_id'])
                deadline=time.monotonic()+180
                while True:
                    state=service.get_run(job['run_id'])
                    if state['status'] not in ('starting','running'): break
                    self.assertLess(time.monotonic(),deadline)
                    time.sleep(.1)
                import psutil
                try: psutil.Process(state['pid']).wait(timeout=10)
                except psutil.NoSuchProcess: pass
                return state,service.get_results(job['run_id'])
            definition={'name':'ordering','hypothesis':'Ordering preserves complete verdicts','strategies':['immediate'],'fleet_sizes':[0,2], 'stop_on_violation':False, 'assertions':[{'type':'hard','metric':'nonconverged_steps','operator':'le','value':0}]}
            ordinary, a=run({**definition,'stress_first':False})
            stressed, b=run({**definition,'stress_first':True})
            self.assertEqual(ordinary['verdict'], 'passed')
            self.assertEqual(stressed['verdict'], ordinary['verdict'])
            def numerical(results):
                return {c['case_id']:{k:v for k,v in c['metrics'].items() if 'seconds' not in k} for c in results['cases']}
            self.assertEqual(numerical(a),numerical(b))
            self.assertTrue(all(c['metrics']['pending_energy_kwh']<1e-6 for c in b['cases']))
            budget,result=run({**definition,'max_runtime_seconds':.00001})
            self.assertEqual(budget['status'],'budget_exceeded')
            self.assertEqual(budget['verdict'],'incomplete')
            stopped,partial=run({**definition,'stop_on_violation':True,'limits':{'max_loading_percent':1}})
            self.assertEqual(stopped['status'],'stopped_on_violation')
            self.assertEqual(stopped['verdict'],'incomplete')
            self.assertTrue(stopped['warning'])
            self.assertEqual(len(partial['cases']),1)
            self.assertEqual(len(partial['cases'][0]['intervals']),1)
            self.assertFalse(partial['evaluation']['complete'])
            self.assertNotEqual(partial['evaluation']['verdict'],'passed')
            from mvgrid.novi_sad.playground.network import build_network
            net,_=build_network()
            fraction=float(net['retained_demand_fraction'])
            self.assertAlmostEqual(fraction,1.0,places=7)
            definition.update(fleet_sizes=[0],demand={'scope':'active_sources'})
            _,active=run(definition)
            city=next(c for c in a['cases'] if c['fleet_size']==0)
            for city_step,active_step in zip(city['intervals'],active['cases'][0]['intervals']):
                self.assertAlmostEqual(city_step['baseline_kw'],active_step['baseline_kw']*fraction,places=6)


if __name__=='__main__': unittest.main()
