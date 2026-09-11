"""Schedule semantics and frozen whole-day benchmark integration."""
import tempfile
import unittest
from mvgrid.novi_sad.playground.charging_profiles import visits
from mvgrid.novi_sad.playground.demand import generate_sessions
from mvgrid.novi_sad.playground.schema import Experiment
from mvgrid.novi_sad.playground.benchmark import BenchmarkService, session_pool
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.districts import validate_district_locations


class ChargingProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.blocks=build_network()

    def test_nested_order_independent_whole_day_and_full_departures(self):
        small=visits(self.blocks,41,100,'whole_day')
        large=visits(list(reversed(self.blocks)),41,3000,'whole_day')
        self.assertEqual(small,large[:100])
        self.assertEqual({s['location_type'] for s in large},{'residential','workplace','public'})
        public=[s for s in large if s['location_type']=='public']
        self.assertTrue(any(s['arrival_step']<16 for s in public))
        self.assertTrue(any(s['arrival_step']>=88 for s in public))
        for s in large:
            self.assertLessEqual(s['departure_step'],132)
            self.assertGreaterEqual((s['departure_step']-s['arrival_step'])*.25*7.4*.9,14)

    def test_home_only_ignores_location_mix_and_public_hubs(self):
        blocks=[dict(id='node',source_id='a',base_weight=1)]
        e=Experiment(name='home',hypothesis='home',fleet={'charging_profile':'home_only','district_mix':{'a':1}})
        validate_district_locations(blocks,e.fleet.model_dump())
        sessions=generate_sessions(e,blocks,9,100)
        self.assertEqual({s['location_type'] for s in sessions},{'residential'})
        self.assertEqual({s['departure_step'] for s in sessions},{132})
        self.assertTrue(all(68<=s['arrival_step']<=84 for s in sessions))

    def test_custom_workplace_mix_matches_experiment_and_shared_generator(self):
        fleet=dict(charging_profile='whole_day',location_mix=dict(residential=0,workplace=1,public=0))
        e=Experiment(name='work',hypothesis='work',fleet=fleet)
        a=generate_sessions(e,self.blocks,5,30)
        self.assertEqual(a,visits(self.blocks,5,30,'whole_day',mix=fleet['location_mix']))
        self.assertTrue(all(28<=s['arrival_step']<=40 and 60<=s['departure_step']<=76 for s in a))

    def test_multiday_public_visits_never_overlap_for_one_vehicle(self):
        mix=dict(residential=0,workplace=0,public=1)
        sessions=visits(self.blocks,43,100,'whole_day',mix=mix,days=4)
        self.assertEqual(len(sessions),400)
        for i in range(100):
            group=sessions[i*4:(i+1)*4]
            self.assertTrue(all(a['departure_step']<=b['arrival_step'] for a,b in zip(group,group[1:])))

    def test_no_missing_location_is_silently_redistributed(self):
        with self.assertRaisesRegex(ValueError,'public'):
            visits([dict(id='x',base_weight=1)],1,0,'whole_day')

    def test_legacy_defaults_remain_explicit(self):
        self.assertEqual(Experiment(name='old',hypothesis='old').fleet.charging_profile,'legacy_mix')
        self.assertEqual(session_pool(self.blocks,41001,10),session_pool(self.blocks,41001,10,charging_profile='home_only'))

    def test_frozen_suite_profile_changes_hash_and_expansion_matches_prefix(self):
        with tempfile.TemporaryDirectory() as root:
            svc=BenchmarkService(root)
            base=dict(name='profiles',standard_fleet=4,max_fleet=4,seeds=[42],district='TELEP',operating_mode='regulated')
            home=svc.create_suite({**base,'charging_profile':'home_only'})
            whole=svc.create_suite({**base,'charging_profile':'whole_day'})
            self.assertNotEqual(home['suite_id'],whole['suite_id'])
            f=svc.get_suite(whole['suite_id'])
            self.assertEqual(len(f['tests']),10)
            for mode in ['city','district','synchronized']:
                expanded=session_pool(f['blocks'],42,30,'TELEP' if mode=='district' else None,mode=='synchronized','whole_day')
                self.assertEqual(f['pools'][mode+'-42'],expanded[:4])
            self.assertIn('location',next(t['title'] for t in f['tests'] if t['id']=='synchronized'))

if __name__=='__main__': unittest.main()
