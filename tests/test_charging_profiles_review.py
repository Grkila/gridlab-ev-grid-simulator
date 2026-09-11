"""Independent invariants for the versioned charging-visit generator.

Offline: no service, network solver, MCP or RL execution.
"""
import unittest

from mvgrid.novi_sad.playground.charging_profiles import visits


BLOCKS = [
    {'id': 'A-HOME', 'delivery_id': 'A', 'kind': 'residential', 'base_weight': .7},
    {'id': 'B-HOME', 'delivery_id': 'B', 'kind': 'residential', 'base_weight': .3},
    {'id': 'A-HUB', 'delivery_id': 'A', 'kind': 'public_hub', 'base_weight': 0.},
    {'id': 'B-HUB', 'delivery_id': 'B', 'kind': 'public_hub', 'base_weight': 0.},
]


class IndependentChargingProfileReview(unittest.TestCase):
    def test_multiday_fleet_prefix_is_stable(self):
        small = visits(BLOCKS, 1234, 11, 'whole_day', days=4)
        large = visits(BLOCKS, 1234, 71, 'whole_day', days=4)
        self.assertEqual(small, large[:len(small)])
        self.assertEqual(large, visits(list(reversed(BLOCKS)), 1234, 71, 'whole_day', days=4))

    def test_multiday_visits_do_not_overlap_and_fit_completion_tail(self):
        rows = visits(BLOCKS, 61001, 1000, 'whole_day', days=7)
        self.assertEqual(len(rows), 7000)
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        self.assertEqual({r['location_type'] for r in rows}, {'residential','workplace','public'})
        by_vehicle = {}
        for row in rows:
            by_vehicle.setdefault(row['id'].rsplit('-d',1)[0], []).append(row)
            self.assertGreater(row['departure_step'], row['arrival_step'])
            self.assertLessEqual(row['departure_step'], 7*96+36)
            self.assertGreaterEqual((row['departure_step']-row['arrival_step'])*.25*row['charger_kw']*row['efficiency'], row['energy_kwh'])
            self.assertEqual(row['block_id'].endswith('HUB'), row['location_type']=='public')
        for vehicle in by_vehicle.values():
            for previous, following in zip(vehicle, vehicle[1:]):
                self.assertLessEqual(previous['departure_step'], following['arrival_step'])

    def test_primary_windows_and_full_day_public_arrivals(self):
        rows = visits(BLOCKS, 41001, 10000, 'whole_day')
        public_arrivals = set()
        for row in rows:
            a,d = row['arrival_step'], row['departure_step']
            if row['location_type']=='residential':
                self.assertTrue(68<=a<=84); self.assertEqual(d,132)
            elif row['location_type']=='workplace':
                self.assertTrue(28<=a<=40); self.assertTrue(60<=d<=76)
            else:
                self.assertTrue(0<=a<=95); self.assertTrue(12<=d-a<=16)
                public_arrivals.add(a)
        self.assertEqual(public_arrivals,set(range(96)))

    def test_synchronized_profile_retains_location_specific_start(self):
        rows = visits(BLOCKS, 61003, 1000, 'whole_day', synchronized=True)
        expected={'residential':72,'workplace':32,'public':48}
        self.assertEqual({r['location_type'] for r in rows},set(expected))
        for row in rows:
            self.assertEqual(row['arrival_step'],expected[row['location_type']])
            if row['location_type']=='public': self.assertTrue(12<=row['departure_step']-48<=16)

    def test_district_restriction_has_no_cross_district_sessions(self):
        rows = visits(BLOCKS, 1234, 1000, 'whole_day', district_mix={'B':1.})
        self.assertEqual({r['district_id'] for r in rows},{'B'})
        self.assertTrue(all(r['block_id'].startswith('B-') for r in rows))
        self.assertEqual(rows[:10],visits(BLOCKS,1234,10,'whole_day',district_mix={'B':1.}))

    def test_home_only_ignores_public_mix_and_needs_no_hub(self):
        rows=visits([BLOCKS[0]],42,30,'home_only',mix={'residential':0.,'workplace':0.,'public':1.})
        self.assertEqual({r['location_type'] for r in rows},{'residential'})
        self.assertEqual({r['departure_step'] for r in rows},{132})

    def test_missing_public_site_rejected_before_random_sampling(self):
        for seed in (0,1,98765):
            with self.assertRaisesRegex(ValueError,'No public charging blocks'):
                visits([BLOCKS[0]],seed,1,'whole_day')


if __name__=='__main__':
    unittest.main()
