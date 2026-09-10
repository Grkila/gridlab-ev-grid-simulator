"""District budgets remain explicit assumptions separate from AC asset ratings."""
import tempfile
import unittest
from unittest.mock import patch
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.districts import resolve_districts
from mvgrid.novi_sad.playground.demand import generate_sessions
from mvgrid.novi_sad.playground.simulation import simulate_case
from mvgrid.novi_sad.playground.service import Service,write_json
from mvgrid.novi_sad.playground.worker import evaluate


class DistrictTests(unittest.TestCase):
    def setUp(self):
        _,self.blocks=build_network()
        self.members=[b for b in self.blocks if b['delivery_id']=='NS5']

    def override(self,capacity,scenario='central'):
        return {'scenario':scenario,'overrides':{'NS5':{'capacity_kw':capacity,'provenance':'Test central estimate'}}}

    def sessions(self):
        return [dict(id=f'ev-{i}',block_id=b['id'],arrival_step=0,departure_step=2,energy_kwh=20,charger_kw=40,efficiency=1) for i,b in enumerate(self.members[:2])]

    def test_shared_budget_across_blocks_and_controller(self):
        options={'district_capacity':self.override(50)}
        immediate=simulate_case(options,[0,0],self.sessions())
        self.assertEqual(len(immediate['intervals']),1)
        self.assertFalse(immediate['complete'])
        self.assertEqual(immediate['metrics']['district_overload_steps'],1)
        self.assertEqual(immediate['metrics']['overload_steps'],0)
        event=next(v for v in immediate['intervals'][0]['violations'] if v['kind']=='district_capacity_exceeded')
        self.assertEqual((event['district_id'],event['value'],event['limit']),('NS5',80,50))
        self.assertEqual(len(event['block_ids']),len(self.members))
        controlled=simulate_case({**options,'strategy':'capacity_aware'},[0,0],self.sessions())
        self.assertEqual(controlled['metrics']['district_overload_steps'],0)
        self.assertLessEqual(controlled['intervals'][0]['ev_kw'],50)
        district=next(d for d in controlled['intervals'][0]['districts'] if d['id']=='NS5')
        self.assertEqual(district['counts']['connected'],2)
        self.assertEqual(district['capacity_kw'],50)
        self.assertEqual(district['headroom_kw'],0)
        self.assertTrue(all(s['district_id']=='NS5' for s in controlled['sessions']))

    def test_sensitivity_scales_fixed_central_override(self):
        capacities=[]
        for scenario in ['low','central','high']:
            d=next(d for d in resolve_districts(self.blocks,self.override(100,scenario)) if d['id']=='NS5')
            self.assertEqual(d['central_capacity_kw'],100)
            capacities.append(d['capacity_kw'])
        self.assertEqual(capacities,[80,100,120])
        low=simulate_case({'district_capacity':self.override(100)},[0],[])
        high=simulate_case({'district_capacity':self.override(100)},[1000],[])
        self.assertEqual(low['resolved_districts'],high['resolved_districts'])

    def test_district_placement_reproducible_and_exclusive(self):
        exp={'name':'placement','hypothesis':'Concentrate vehicles','fleet':{'district_mix':{'NS5':1}}}
        first=generate_sessions(exp,self.blocks,12,100)
        self.assertEqual(first,generate_sessions(exp,self.blocks,12,100))
        self.assertEqual({s['district_id'] for s in first},{'NS5'})
        self.assertTrue({s['block_id'] for s in first}<={b['id'] for b in self.members})
        exp['fleet']['district_mix']={'NS5':.4,'NS7':.6}
        first=generate_sessions(exp,self.blocks,12,100)
        exp['fleet']['district_mix']={'NS7':.6,'NS5':.4}
        self.assertEqual(first,generate_sessions(exp,self.blocks,12,100))

    def test_unknown_ids_and_invalid_overrides_rejected(self):
        with tempfile.TemporaryDirectory() as home:
            service=Service(home)
            base={'name':'validation','hypothesis':'Reject unknown districts'}
            for update in [{'fleet':{'district_mix':{'UNKNOWN':1}}},{'district_capacity':{'overrides':{'UNKNOWN':{'capacity_kw':1,'provenance':'test'}}}},{'district_capacity':self.override(-1)},{'fleet':{'district_mix':{'NS5':.2}}}]:
                with self.assertRaises(ValueError):service.validate_experiment({**base,**update})
            self.assertEqual(len(service.catalog()['districts']),10)
            self.assertEqual(len(service.validate_experiment(base)['resolved_districts']),10)

    def test_upstream_violation_remains_separate(self):
        options={'district_capacity':{'overrides':{d['id']:{'capacity_kw':1e9,'provenance':'Test unrestrictive budget'} for d in resolve_districts(self.blocks)}}}
        result=simulate_case(options,[400000],[])
        self.assertEqual(result['metrics']['district_overload_steps'],0)
        self.assertTrue(result['metrics']['overload_steps'] or result['metrics']['nonconverged_steps'])

    def test_stopped_district_assertion_is_counterexample(self):
        result=simulate_case({'district_capacity':self.override(50)},[0,0],self.sessions())
        result['case_id']='case-0'
        for metric in ('district_overload_steps','max_district_loading_percent'):
            config={'assertions':[dict(type='hard',metric=metric,operator='le',value=0 if metric=='district_overload_steps' else 100)]}
            verdict=evaluate(config,[result],False)
            self.assertEqual(verdict['verdict'],'failed')
            self.assertTrue(verdict['assertions'][0]['counterexamples'][0]['first_interval'])

    def test_changed_capacity_is_not_pure_controller_comparison(self):
        with tempfile.TemporaryDirectory() as home:
            service=Service(home)
            records=[{'run':{'status':'completed','experiment_id':f'exp-{i}'},'evaluation':{'complete':True},'cases':[]} for i in range(2)]
            for i in range(2):write_json(service._path('runs',f'run-{i}')/'manifest.json',{'fingerprint':{'same':True}})
            definitions=[{'definition':{'district_capacity':self.override(v)}} for v in (100,200)]
            with patch.object(service,'get_results',side_effect=records),patch.object(service,'get_experiment',side_effect=definitions):
                result=service.compare_runs(['run-0','run-1'])
            self.assertFalse(result['paired_compatible'])
            self.assertIn('district_capacity',result['differing_fields'])


if __name__=='__main__':unittest.main()
