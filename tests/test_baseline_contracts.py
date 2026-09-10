import copy
import unittest
from unittest.mock import patch
import pandapower as pp

from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.simulation import Simulator


class BaselineContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network, cls.blocks = build_network()

    def simulator(self, case=None, sessions=None):
        sim = Simulator()
        sessions = sessions if sessions is not None else [self.session()]
        with patch('mvgrid.novi_sad.playground.simulation.build_network',
                   return_value=(copy.deepcopy(self.network), copy.deepcopy(self.blocks))):
            sim.reset(case or {}, [0.] * 200, sessions)
        return sim

    def session(self, **values):
        return dict(dict(id='a', block_id=self.blocks[0]['id'], arrival_step=0,
                         departure_step=190, energy_kwh=100., charger_kw=4., efficiency=1.), **values)

    def test_nonfinite_direct_inputs_rejected(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(field='dt_hours', value=value), self.assertRaises(ValueError):
                self.simulator({'dt_hours': value})
            for field in ('energy_kwh', 'charger_kw', 'efficiency', 'arrival_step', 'departure_step'):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.simulator(sessions=[self.session(**{field: value})])
        for value in (.5, True):
            with self.subTest(index=value), self.assertRaises(ValueError):
                self.simulator(sessions=[self.session(arrival_step=value)])

    def test_fixed_release_calendar_boundaries(self):
        cases = [(72, 23, 91, 0.), (72, 23, 92, 4.), (72, 23, 96, 4.),
                 (94, 23, 94, 4.), (72, 0, 72, 4.), (2, 23, 32, 0.)]
        for arrival, hour, step, expected in cases:
            with self.subTest(arrival=arrival, hour=hour, step=step):
                sim = self.simulator({'strategy': 'fixed_delay', 'fixed_start_hour': hour},
                                     [self.session(arrival_step=arrival)])
                sim.index = step
                _, interval, _ = sim.step()
                self.assertEqual(interval['ev_kw'], expected)
        sim = self.simulator({'strategy': 'fixed_delay', 'fixed_start_hour': 23},
                             [self.session(arrival_step=72, departure_step=92)])
        sim.index = 92
        self.assertEqual(sim.step()[1]['ev_kw'], 0.)

    def test_randomized_support_and_input_order_invariance(self):
        sessions = [self.session(id=str(i)) for i in range(300)]
        first = self.simulator({'strategy': 'randomized_delay', 'seed': 17}, sessions)
        second = self.simulator({'strategy': 'randomized_delay', 'seed': 17}, list(reversed(sessions)))
        draws = lambda sim: {s['id']: s['delay_jitter'] for s in sim.sessions}
        self.assertEqual(draws(first), draws(second))
        self.assertEqual(set(draws(first).values()), set(range(16)))

    def test_randomized_release_crosses_midnight_and_is_not_arrival_relative(self):
        sim = self.simulator({'strategy': 'randomized_delay', 'fixed_start_hour': 23},
                             [self.session(arrival_step=72)])
        sim.sessions[0]['delay_jitter'] = 15
        sim.index = 106
        self.assertEqual(sim.step()[1]['ev_kw'], 0.)
        self.assertEqual(sim.step()[1]['ev_kw'], 4.)
        sim = self.simulator({'strategy': 'randomized_delay', 'fixed_start_hour': 0},
                             [self.session(arrival_step=72)])
        sim.sessions[0]['delay_jitter'] = 0
        sim.index = 72
        self.assertEqual(sim.step()[1]['ev_kw'], 4.)

    def test_external_capacity_requests_keep_admission_and_ac_shield(self):
        hub = next(b for b in self.blocks if b.get('kind') == 'public_hub')
        session = self.session(block_id=hub['id'], charger_kw=10000., energy_kwh=2000.)
        builtin = self.simulator({'strategy': 'capacity_aware'}, [session]).step()[1]
        external = self.simulator({'strategy': 'capacity_aware'}, [session]).step({'a': 10000.})[1]
        self.assertGreater(external['curtailed_ev_kw'], 0.)
        self.assertEqual(external['applied_actions_kw'], builtin['applied_actions_kw'])
        self.assertEqual(external['safety_iterations'], builtin['safety_iterations'])
        self.assertLessEqual(external['max_line_loading_percent'], 100.)

    def test_external_capacity_requests_trigger_ac_recheck(self):
        sim = self.simulator({'strategy': 'capacity_aware'})
        runpp = pp.runpp
        calls = []
        def first_attempt_undervoltage(net, **kwargs):
            runpp(net, **kwargs)
            calls.append(True)
            if len(calls) == 1:
                net.res_bus.loc[:, 'vm_pu'] = .90
        with patch('mvgrid.novi_sad.playground.simulation.pp.runpp', side_effect=first_attempt_undervoltage):
            interval = sim.step({'a': 4.})[1]
        self.assertEqual(interval['safety_iterations'], 1)
        self.assertEqual(len(calls), 2)
        self.assertAlmostEqual(interval['ev_kw'], 2.)


if __name__ == '__main__':
    unittest.main()
