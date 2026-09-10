import copy, unittest
from unittest.mock import patch
from mvgrid.novi_sad.playground.simulation import Simulator
from mvgrid.novi_sad.playground.strategies import ChargingController, capacity_constraints, baseline_at, connected_sessions

class StrategyIndependentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template=Simulator(); cls.template.reset({},[1000.]*12,[])
        cls.block=cls.template.blocks[0]['id']
    def sim(self,sessions):
        s=copy.deepcopy(self.template)
        s.sessions=[dict(block_id=self.block,arrival_step=0,departure_step=4,energy_kwh=4.,remaining_kwh=4.,delivered_kwh=0.,charger_kw=8.,efficiency=1.,**x) for x in sessions]
        return s
    def test_causality(self):
        for name in ('least_laxity_first','mpc','valley_filling','voltage_responsive'):
            a=self.sim([{'id':'a'}]); b=copy.deepcopy(a)
            b.demand[1:]=[999999.]*11
            b.sessions.append(dict(id='future',block_id=self.block,arrival_step=1,departure_step=3,remaining_kwh=999.,energy_kwh=999.,charger_kw=100.,efficiency=1.))
            self.assertEqual(ChargingController(name).actions(a),ChargingController(name).actions(b),name)
    def test_valley_flatten(self):
        s=self.sim([{'id':'a'}]); c=ChargingController('valley_filling'); actions=c.actions(s)
        self.assertAlmostEqual(actions['a'],4.,places=6)
    def test_mpc_flatten(self):
        s=self.sim([{'id':'a'}]); c=ChargingController('mpc'); actions=c.actions(s)
        self.assertAlmostEqual(actions['a'],4.,places=5)
    def test_llf_not_departure(self):
        s=self.sim([{'id':'a'},{'id':'b'}]); s.sessions[0].update(departure_step=2,remaining_kwh=.1); s.sessions[1].update(departure_step=4,remaining_kwh=7.9)
        with patch('mvgrid.novi_sad.playground.strategies.capacity_constraints',return_value=[(__import__('numpy').array([1.,1.]),8.)]):
            a=ChargingController('least_laxity_first').actions(s)
        self.assertEqual(a['b'],8.); self.assertEqual(a['a'],0.)
    def test_mpc_infeasible(self):
        s=self.sim([{'id':'a'}]); s.sessions[0].update(remaining_kwh=20.,energy_kwh=20.)
        c=ChargingController('mpc'); self.assertAlmostEqual(c.actions(s)['a'],8.,places=5)
        self.assertAlmostEqual(c.last['predicted_shortfall_kwh'],12.,places=5)
    def test_voltage_observation_and_recovery(self):
        s=self.sim([{'id':'a'}]); c=ChargingController('voltage_responsive')
        self.assertEqual(c.actions(s)['a'],0.)
        c.observe(s,dict(converged=True,blocks=[dict(id=self.block,voltage_pu=1.)],applied_actions_kw={'a':2.}))
        self.assertEqual(c.actions(s)['a'],4.)
        c.observe(s,dict(converged=False,blocks=[],applied_actions_kw={'a':0.}))
        self.assertEqual(c.actions(s)['a'],0.)
    def test_voltage_remaining_bound(self):
        s=self.sim([{'id':'a'}]); s.sessions[0]['remaining_kwh']=.01
        c=ChargingController('voltage_responsive'); c.voltages[self.block]=1.; a=c.actions(s)
        self.assertLessEqual(a['a'],.01/s.dt)
    def test_previous_day_preserves_current_measurement(self):
        s=self.sim([{'id':'a'}]); s.index=96; s.demand=[1000.]*97
        s.intervals=[{'blocks':[{'id':b['id'],'baseline_kw':1.} for b in s.blocks]} for _ in range(96)]
        c=ChargingController('mpc',{'forecast':'previous_day'})
        self.assertEqual(c.forecast(s,2)[0],baseline_at(s,96))

    def test_step_rejects_missing_strategy_controller(self):
        s=self.sim([{'id':'a'}])
        for name in ('least_laxity_first','mpc','valley_filling','voltage_responsive'):
            s.case['strategy']=name
            with self.assertRaises(ValueError,msg=name): s.step()

    def test_real_simulator_four_strategies(self):
        from mvgrid.novi_sad.playground.simulation import simulate_case
        session=dict(id='a',block_id=self.block,arrival_step=0,departure_step=4,energy_kwh=2.,charger_kw=8.,efficiency=1.)
        for name in ('least_laxity_first','mpc','valley_filling','voltage_responsive'):
            r=simulate_case({'strategy':name,'stop_on_violation':False},[1000.]*4,[session])
            self.assertTrue(r['complete'],name)
            self.assertGreater(r['metrics']['delivered_energy_kwh'],0,name)
            self.assertLessEqual(r['metrics']['delivered_energy_kwh'],2.+1e-6,name)
            self.assertTrue(all('controller' in i for i in r['intervals']),name)
            self.assertTrue(all(not i['violations'] for i in r['intervals']),name)

    def test_mpc_failure_fallback(self):
        from types import SimpleNamespace
        s=self.sim([{'id':'a'}]); c=ChargingController('mpc')
        with patch('scipy.optimize.linprog',return_value=SimpleNamespace(success=False,message='test timeout')):
            self.assertEqual(c.actions(s)['a'],8.)
        self.assertIn('failed',c.last['fallback'])

if __name__=='__main__': unittest.main()

