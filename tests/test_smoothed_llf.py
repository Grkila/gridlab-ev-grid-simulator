import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from mvgrid.novi_sad.playground.smoothed_llf import allocate
from mvgrid.novi_sad.playground.strategies import ChargingController


def ev(name, energy=1., rate=1., efficiency=1., departure=2):
    return dict(id=name, remaining_kwh=energy, charger_kw=rate,
                efficiency=efficiency, departure_step=departure)


class SmoothedLLFTests(unittest.TestCase):
    def test_equal_laxity_shares_instead_of_greedy_tie_break(self):
        actions, _ = allocate([ev('a'), ev('b')], 0, 1., [(np.ones(2), 1.)])
        np.testing.assert_allclose(list(actions.values()), [.5, .5], atol=1e-7)

    def test_paper_oscillation_example(self):
        # Paper footnote 6: laxities 1.25 and .75. Next laxities become .5/.5.
        actions, _ = allocate([ev('a', .75), ev('b', 1.25)], 0, 1., [(np.ones(2), 1.)])
        np.testing.assert_allclose(list(actions.values()), [.25, .75], atol=1e-7)

    def test_efficiency_and_heterogeneous_charger_mapping(self):
        # Both need one hour at their rating, so equal laxity -> equal fractions.
        actions, _ = allocate([ev('a', 1., 2., .5), ev('b', 1., 1., 1.)], 0, .5, [(np.ones(2), 1.5)])
        np.testing.assert_allclose(list(actions.values()), [1., .5], atol=1e-6)

    def test_overlapping_constraints_solve_jointly(self):
        rows = [(np.array([1., 1., 0.]), 1.), (np.array([0., 1., 1.]), 1.)]
        actions, _ = allocate([ev('a'), ev('b'), ev('c')], 0, 1., rows)
        # C=2 and equal base=0. QP stationarity: 2*(x-2)=(1-x)-2,
        # so shared EV b=0 and outer EVs a=c=1. This is the explicit Eq6
        # quadratic utility extension, not single-budget max-min equalization.
        np.testing.assert_allclose(list(actions.values()), [1., 0., 1.], atol=1e-6)
        for weights, budget in rows:
            self.assertLessEqual(float(weights @ list(actions.values())), budget + 1e-8)

    def test_nonuniform_positive_coefficients(self):
        rows = [(np.array([.5, 1.]), .75), (np.array([1., .25]), .9)]
        actions, _ = allocate([ev('a'), ev('b')], 0, 1., rows)
        for weights, budget in rows:
            self.assertLessEqual(float(weights @ list(actions.values())), budget + 1e-8)
        self.assertGreater(min(actions.values()), 0.)

    def test_zero_headroom_does_not_curtail_disjoint_charger(self):
        actions, _ = allocate([ev('a'), ev('b')], 0, 1., [(np.array([1., 0.]), 0.)])
        self.assertEqual(actions, {'a': 0., 'b': 1.})

    def test_remaining_battery_energy_cap(self):
        actions, _ = allocate([ev('a', .1, 1., .5)], 0, .5, [])
        self.assertAlmostEqual(actions['a'], .4)

    def test_solver_failure_and_timeout_record_plain_fallback(self):
        sessions = [ev('a'), ev('b')]
        sim = SimpleNamespace(index=0, dt=1., observation=lambda: {'sessions': sessions})
        for error in (RuntimeError('test failed'), TimeoutError('test timeout')):
            controller = ChargingController('least_laxity_first')
            with patch('mvgrid.novi_sad.playground.strategies.baseline_at', return_value={}), \
                 patch('mvgrid.novi_sad.playground.strategies.capacity_constraints', return_value=[(np.ones(2), 1.)]), \
                 patch('mvgrid.novi_sad.playground.smoothed_llf.allocate', side_effect=error):
                self.assertEqual(controller.actions(sim), {'a': 1., 'b': 0.})
            self.assertIn('plain_least_laxity_first', controller.last['fallback'])

    def test_controller_preserves_smoothed_feasible_action(self):
        sessions = [ev('a'), ev('b')]
        sim = SimpleNamespace(index=0, dt=1., observation=lambda: {'sessions': sessions})
        controller = ChargingController('least_laxity_first')
        with patch('mvgrid.novi_sad.playground.strategies.baseline_at', return_value={}), \
             patch('mvgrid.novi_sad.playground.strategies.capacity_constraints', return_value=[(np.ones(2), 1.)]), \
             patch('mvgrid.novi_sad.playground.strategies.project_headroom', side_effect=AssertionError('greedy projection')):
            np.testing.assert_allclose(list(controller.actions(sim).values()), [.5, .5], atol=1e-7)
        self.assertIsNone(controller.last['fallback'])

    def test_budget_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'size budget'):
            allocate([ev('a'), ev('b')], 0, 1., [], max_variables=1)


if __name__ == '__main__':
    unittest.main()
