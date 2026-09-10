import copy
import unittest
from unittest.mock import patch

from pandapower.powerflow import LoadflowNotConverged
from mvgrid.novi_sad.playground.simulation import Simulator
from mvgrid.novi_sad.playground.strategies import ChargingController
from mvgrid.novi_sad.playground.districts import district_id


class VoltageBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template=Simulator()
        cls.template.reset({'strategy':'voltage_responsive'},[1000.],[])

    def simulator(self,dt=.25):
        sim=copy.deepcopy(self.template)
        sim.dt=dt
        sim.sessions=[dict(id='a',block_id=sim.blocks[0]['id'],arrival_step=0,
                           district_id=district_id(sim.blocks[0]),
                           departure_step=1,energy_kwh=2.,remaining_kwh=2.,
                           delivered_kwh=0.,charger_kw=8.,efficiency=1.)]
        return sim

    def test_one_slot_charges_without_bootstrap_time_or_energy_advance(self):
        sim=self.simulator()
        controller=ChargingController('voltage_responsive')
        before=sim.net.load.copy(deep=True)
        action=controller.actions(sim)
        self.assertGreater(action['a'],0.)
        self.assertEqual(sim.index,0)
        self.assertEqual(sim.intervals,[])
        self.assertEqual(sim.sessions[0]['delivered_kwh'],0.)
        self.assertTrue(before.equals(sim.net.load))
        _,interval,_=sim.step(action)
        controller.observe(sim,interval)
        self.assertGreater(sim.sessions[0]['delivered_kwh'],0.)
        self.assertIn('raw_policy_kw',interval['controller'])

    def test_nonconvergent_bootstrap_requests_zero(self):
        sim=self.simulator()
        controller=ChargingController('voltage_responsive')
        with patch('mvgrid.novi_sad.playground.simulation.pp.runpp',side_effect=LoadflowNotConverged('test')):
            self.assertEqual(controller.actions(sim)['a'],0.)
        self.assertEqual(controller.last['voltage_bootstrap'],'measurement_unavailable')

    def test_recovery_scales_with_elapsed_time(self):
        for dt,expected in ((.125,1.),(.25,2.),(.5,4.)):
            sim=self.simulator(dt)
            controller=ChargingController('voltage_responsive')
            with patch.object(sim,'measure_baseline_voltages',return_value={sim.blocks[0]['id']:1.}):
                self.assertAlmostEqual(controller.actions(sim)['a'],expected)

    def test_applied_intervention_is_visible(self):
        sim=self.simulator()
        controller=ChargingController('voltage_responsive')
        controller.last={'requested_kw':2.}
        interval={'converged':True,'blocks':[], 'applied_actions_kw':{'a':.5}}
        controller.observe(sim,interval)
        self.assertEqual(interval['controller']['raw_policy_kw'],2.)
        self.assertEqual(interval['controller']['applied_kw'],.5)
        self.assertEqual(interval['controller']['safety_curtailed_kw'],1.5)
        self.assertTrue(interval['controller']['safety_intervened'])
        self.assertIn('mandatory',interval['controller']['safety_overlay'])


if __name__=='__main__':
    unittest.main()
