"""Independent numerical and state-contract checks for continuous node control."""
import copy
from types import SimpleNamespace
import pandas as pd
import unittest
from unittest.mock import patch
import numpy as np

try:
    from mvgrid.novi_sad.playground.continuous_env import ContinuousEVEnv, grid_severity
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

NODES = [f'n{i:02}' for i in range(52)]


class TinySimulator:
    def reset(self, case, demand, sessions, on_baseline_step=None):
        self.case = case
        self.demand = list(demand)
        self.dt = .25
        self.index = 0
        self.intervals = []
        self.net = SimpleNamespace(res_bus=pd.DataFrame({'vm_pu': [1.]*52}), get=lambda key, default=None: default)
        self.blocks = [dict(id=n, bus_index=NODES.index(n), base_weight=1/52, capacity_kw=100., source_id='s',
                            source_capacity_kw=5200., delivery_id='d') for n in NODES]
        self.by_id = {b['id']: b for b in self.blocks}
        self.resolved_districts = [dict(id='d', capacity_kw=5200.)]
        self.district_by_id = {'d': self.resolved_districts[0]}
        self.sessions = copy.deepcopy(sessions)
        self.vehicle_count = len(sessions)
        for s in self.sessions:
            s.update(remaining_kwh=s['energy_kwh'], delivered_kwh=0.)

    def measure_baseline_voltages(self):
        return {n: 1. for n in NODES}

    def step_node_loads(self, targets):
        budgets = dict(targets)
        allocations = {}
        for s in sorted(self.sessions, key=lambda s: (s['departure_step'], s['id'])):
            if not s['arrival_step'] <= self.index < s['departure_step']:
                continue
            p = min(budgets[s['block_id']], s['charger_kw'], s['remaining_kwh']/(self.dt*s['efficiency']))
            budgets[s['block_id']] -= p
            allocations[s['id']] = p
            s['remaining_kwh'] -= p*self.dt*s['efficiency']
            s['delivered_kwh'] += p*self.dt*s['efficiency']
        total = self.demand[self.index]+sum(allocations.values())
        valid = not self.case.get('numerical_failure')
        interval = dict(step=self.index, applied_actions_kw=allocations,
                        converged=valid, violations=self.case.get('violations', []),
                        supply_kw=total if valid else None, total_kw=total,
                        min_voltage_pu=1. if valid else None)
        self.intervals.append(interval)
        self.index += 1
        return {}, interval, self.index >= len(self.demand)


def factory(seed):
    return dict(case={}, demand_kw=[52.]*4, sessions=[dict(id='ev', block_id=NODES[0],
        energy_kwh=1., charger_kw=8., efficiency=1., arrival_step=0, departure_step=4)])


@unittest.skipUnless(AVAILABLE, 'optional continuous RL dependencies unavailable')
class ContinuousEnvTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('mvgrid.novi_sad.playground.continuous_env.Simulator', TinySimulator)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def env(self, fn=factory):
        return ContinuousEVEnv(fn, NODES)

    def test_physical_caps_and_exact_reward_terms(self):
        env = self.env()
        obs, _ = env.reset(seed=7)
        self.assertTrue(env.observation_space.contains(obs))
        _, reward, terminal, truncated, info = env.step(np.ones(52))
        d = info['continuous']
        self.assertEqual(d['requested_node_kw'][NODES[0]], 8.)
        self.assertEqual(d['allocated_node_kw'][NODES[0]], 4.)
        self.assertEqual(d['executed_node_kw'][NODES[0]], 4.)
        self.assertEqual(d['physical_cap_kwh'], 1.)
        self.assertAlmostEqual(reward, 1.-.1-.05*56./5200.)
        self.assertFalse(terminal or truncated)
        self.assertEqual(env.sim.case['strategy'], 'immediate')
        self.assertFalse(env.sim.case['stop_on_violation'])
        self.assertFalse(d['grid_rescue_enabled'])

    def test_departure_penalty_exactly_once_and_no_zero_energy_pass(self):
        env = self.env()
        env.reset(seed=1)
        terms = []
        for _ in range(4):
            _, _, terminal, truncated, info = env.step(-np.ones(52))
            terms.append(info['continuous']['reward_terms']['shortfall'])
        self.assertEqual(terms, [0., 0., 0., -20.])
        self.assertTrue(terminal)
        self.assertFalse(truncated)
        self.assertTrue(info['episode_metrics']['complete'])
        self.assertFalse(info['episode_metrics']['passed'])
        self.assertEqual(info['episode_metrics']['unmet_energy_kwh'], 1.)
        with self.assertRaises(RuntimeError):
            env.step(np.zeros(52))

    def test_grid_violation_not_rescued_or_silently_terminal(self):
        def bad(seed):
            f = factory(seed)
            f['case']['violations'] = [dict(kind='undervoltage', asset_type='bus',
                asset_id='b', value=.9, limit=.95)]*2
            return f
        env = self.env(bad)
        env.reset(seed=1)
        _, _, terminated, _, info = env.step(np.ones(52))
        self.assertFalse(terminated)
        self.assertAlmostEqual(info['continuous']['reward_terms']['grid'], -20*(1+.05/.95))
        self.assertFalse(info['episode_metrics']['passed'])

    def test_snapshot_reproduces_next_step_and_rng_reset(self):
        env = self.env()
        env.reset(seed=93)
        env.step(-np.ones(52))
        snapshot = env.get_state()
        expected = env.step(np.zeros(52))
        restored = self.env()
        restored.set_state(snapshot)
        actual = restored.step(np.zeros(52))
        np.testing.assert_array_equal(expected[0], actual[0])
        self.assertEqual(expected[1:4], actual[1:4])
        self.assertEqual(expected[4]['continuous'], actual[4]['continuous'])
        self.assertEqual(env.reset()[1]['episode_seed'], restored.reset()[1]['episode_seed'])
        snapshot['node_ids'].reverse()
        with self.assertRaises(ValueError):
            restored.set_state(snapshot)

    def test_future_sessions_and_demand_are_not_observed(self):
        def future(seed):
            f = factory(seed)
            f['demand_kw'][2] = 9999.
            f['sessions'].append(dict(f['sessions'][0], id='future', arrival_step=2, energy_kwh=50.))
            return f
        a, b = self.env(), self.env(future)
        np.testing.assert_array_equal(a.reset(seed=1)[0], b.reset(seed=1)[0])

    def test_invalid_and_time_limit_remain_nonpassing(self):
        env = self.env()
        env.reset(seed=1, options={'max_steps': 1})
        _, _, terminated, truncated, info = env.step(np.ones(52))
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertFalse(info['episode_metrics']['complete'])
        self.assertFalse(info['episode_metrics']['passed'])
        def bad(seed):
            f = factory(seed)
            f['case']['numerical_failure'] = True
            return f
        env = self.env(bad)
        env.reset(seed=1)
        obs, _, terminated, truncated, info = env.step(np.ones(52))
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertTrue(np.isfinite(obs).all())
        self.assertFalse(info['episode_metrics']['complete'])
        self.assertEqual(info['continuous']['reward_terms']['numerical_failure'], -20.)

    def test_invalid_shapes_and_incomplete_departure_horizon_rejected(self):
        env = self.env()
        env.reset(seed=1)
        for action in (np.ones(51), np.full(52, np.nan)):
            with self.assertRaises(ValueError):
                env.step(action)
        with self.assertRaises(ValueError):
            ContinuousEVEnv(factory, NODES[:-1])
        def short(seed):
            f = factory(seed)
            f['demand_kw'] = [52.]
            return f
        with self.assertRaises(ValueError):
            self.env(short).reset(seed=1)


@unittest.skipUnless(AVAILABLE, 'optional continuous RL dependencies unavailable')
class RealContinuousEnvTests(unittest.TestCase):
    def test_real_power_flow_full_delivery_and_restore(self):
        from mvgrid.novi_sad.playground.network import build_network
        _, blocks = build_network()
        nodes = sorted(b['id'] for b in blocks)
        def real(seed):
            return dict(case={'seed': seed}, demand_kw=[50000.]*2,
                        sessions=[dict(id='a', block_id=nodes[0], arrival_step=0,
                        departure_step=2, energy_kwh=.5, charger_kw=7.4, efficiency=.9)])
        env = ContinuousEVEnv(real, nodes)
        env.reset(seed=2)
        env.step(np.ones(52))
        saved = env.get_state()
        expected = env.step(np.ones(52))
        env.set_state(saved)
        actual = env.step(np.ones(52))
        self.assertAlmostEqual(expected[1], actual[1])
        self.assertTrue(actual[4]['episode_metrics']['complete'])
        self.assertAlmostEqual(actual[4]['episode_metrics']['delivered_energy_kwh'], .5)
        self.assertEqual(actual[4]['episode_metrics']['unmet_energy_kwh'], 0.)


if __name__ == '__main__':
    unittest.main()
