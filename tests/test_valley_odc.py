import unittest
from types import SimpleNamespace

import numpy as np
from scipy.optimize import minimize

from mvgrid.novi_sad.playground.valley_odc import solve_odc
from mvgrid.novi_sad.playground.strategies import ChargingController


class ValleyODCTests(unittest.TestCase):
    def test_first_iteration_is_simultaneous_proximal_update(self):
        # N=2, p=[0,4], alpha=1. Both EV subproblems give [2,0].
        # Sequential coordinate descent would instead produce [2,0],[1,1].
        schedule, info = solve_odc([0., 4.], np.full((2, 2), 8.), [2., 2.], 1)
        np.testing.assert_allclose(schedule, [[2., 0.], [2., 0.]], atol=1e-12)
        self.assertEqual(info['odc_alpha'], 1.)

    def test_heterogeneous_solution_matches_independent_qp(self):
        baseline = np.array([5., 0., 2., 1.])
        upper = np.array([[3., 3., 0., 0.], [2., 2., 2., 2.], [0., 1., 1., 1.]])
        energy = np.array([4., 3., 2.])
        schedule, info = solve_odc(baseline, upper, energy, 2000)
        objective = lambda x: np.sum((baseline + x.reshape(3, 4).sum(axis=0)) ** 2)
        equality = lambda x: x.reshape(3, 4).sum(axis=1) - energy
        start = upper * (energy / upper.sum(axis=1))[:, None]
        optimum = minimize(objective, start.ravel(), method='SLSQP',
                           bounds=[(0., u) for u in upper.ravel()],
                           constraints={'type': 'eq', 'fun': equality},
                           options={'ftol': 1e-11, 'maxiter': 1000})
        self.assertTrue(optimum.success, optimum.message)
        self.assertAlmostEqual(objective(schedule), optimum.fun, places=7)
        np.testing.assert_allclose(schedule.sum(axis=1), energy, atol=1e-10)
        self.assertTrue(info['converged'])

    def test_iteration_limit_is_not_convergence(self):
        _, info = solve_odc([0., 4.], [[8., 0.], [8., 8.]], [4., 4.], 1)
        self.assertFalse(info['converged'])
        self.assertEqual(info['solver_status'], 'odc_iteration_limit')
        self.assertGreater(info['fixed_point_residual_kw'], 0.)

    def test_infeasible_energy_is_reported(self):
        controller = ChargingController('valley_filling')
        sim = SimpleNamespace(dt=.25, index=0)
        session = dict(id='a', departure_step=4, remaining_kwh=20., charger_kw=8., efficiency=1.)
        action = controller._valley(sim, [session], [{'b': 1000.}] * 4)
        self.assertAlmostEqual(action['a'], 8.)
        self.assertAlmostEqual(controller.last['predicted_shortfall_kwh'], 12.)
        self.assertFalse(controller.last['paper_energy_constraints_feasible'])

    def test_efficiency_and_different_deadlines(self):
        controller = ChargingController('valley_filling', {'valley_iterations': 50})
        sessions = [dict(id='a', departure_step=2, remaining_kwh=1., charger_kw=8., efficiency=.5),
                    dict(id='b', departure_step=4, remaining_kwh=1., charger_kw=8., efficiency=1.)]
        action = controller._valley(SimpleNamespace(dt=.25, index=0), sessions, [{'b': 0.}] * 4)
        self.assertAlmostEqual(action['a'], 4., places=6)
        self.assertAlmostEqual(action['b'], 0., places=6)
        self.assertAlmostEqual(controller.last['required_horizon_energy_kwh'], 2.)
        self.assertAlmostEqual(controller.last['predicted_shortfall_kwh'], 0.)


if __name__ == '__main__':
    unittest.main()
