"""Coupled deadline regressions for the linear planning controller."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from mvgrid.novi_sad.playground.strategies import ChargingController


class MPCDeadlineTests(unittest.TestCase):
    def simulator(self, count=2, departure=2):
        sessions=[dict(id=str(i), block_id='block', departure_step=departure,
                       charger_kw=1., remaining_kwh=1., efficiency=1.)
                  for i in range(count)]
        return SimpleNamespace(index=0, dt=1., intervals=[], sessions=sessions,
                               observation=lambda: {'sessions':sessions})

    def test_short_requested_horizon_preserves_shared_deadline_feasibility(self):
        sim=self.simulator()
        controller=ChargingController('mpc', {'horizon_steps':1})
        with patch('mvgrid.novi_sad.playground.strategies.baseline_at', return_value={'block':0.}), \
             patch('mvgrid.novi_sad.playground.strategies.capacity_constraints', return_value=[(np.ones(2),1.)]):
            for step in range(2):
                sim.index=step
                actions=controller.actions(sim)
                self.assertLessEqual(sum(actions.values()),1.+1e-7)
                if step==0:
                    self.assertTrue(controller.last['horizon_extended'])
                    self.assertEqual(controller.last['effective_horizon_steps'],2)
                    self.assertEqual(controller.last['optimization_variables'],7)
                    self.assertGreater(sum(actions.values()),.999)
                for session in sim.sessions:
                    session['remaining_kwh']-=actions.get(session['id'],0.)
        self.assertLess(sum(s['remaining_kwh'] for s in sim.sessions),1e-5)

    def test_guard_counts_deficits_and_peak_variable(self):
        # 10 * 9 power variables fit 100, but 10 deficits + peak do not.
        sim=self.simulator(count=10,departure=9)
        controller=ChargingController('mpc',{'horizon_steps':1,'max_variables':100})
        with patch('mvgrid.novi_sad.playground.strategies.baseline_at', return_value={'block':0.}), \
             patch('mvgrid.novi_sad.playground.strategies.capacity_constraints', return_value=[(np.ones(10),10.)]), \
             patch.object(controller,'_mpc') as solve:
            controller.actions(sim)
        solve.assert_not_called()
        self.assertEqual(controller.last['optimization_variables'],101)
        self.assertEqual(controller.last['effective_horizon_steps'],9)
        self.assertIn('variable budget exceeded',controller.last['fallback'])
        self.assertIsNone(controller.last['solver_status'])


if __name__=='__main__':
    unittest.main()
