"""Independent contracts for reproducibility and honest capacity comparisons."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mvgrid.novi_sad.playground.benchmark import (
    TESTS, BenchmarkConfig, BenchmarkService, aggregate_trials, fleet_ladder,
    session_pool, trial_summary, run_benchmark, refine_capacity_boundary, capacity_counts,
)
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.service import digest, implementation_fingerprint, read_json, write_json


def measured(count, fail=False):
    requested = count*14.
    unmet = 1. if fail and count else 0.
    intervals = [dict(step=t, total_kw=100+count, ev_kw=count, converged=True,
                      min_voltage_pu=.98, violations=[], safety_iterations=0,
                      capacity_layers=[dict(loading_percent=50+count, headroom_kw=50-count)],
                      districts=[dict(loading_percent=60+count, headroom_kw=40-count)]) for t in range(132)]
    return dict(complete=True, metrics=dict(requested_energy_kwh=requested, delivered_energy_kwh=requested-unmet,
                unmet_energy_kwh=unmet, pending_energy_kwh=0., peak_demand_kw=100+count,
                min_voltage_pu=.98, runtime_seconds=1., nonconverged_steps=0), intervals=intervals)


class BenchmarkContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.blocks = build_network()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.service = BenchmarkService(self.temp.name)

    def suite(self):
        return self.service.create_suite(dict(name='Test', standard_fleet=2, max_fleet=4, seeds=[41001]))

    def prepared(self, suite):
        job_id = 'bench-test'
        folder = self.service.path('benchmarks', job_id)
        fingerprint = implementation_fingerprint()
        write_json(folder/'request.json', dict(suite_id=suite['suite_id'], fingerprint=fingerprint,
                   implementation_id=digest(fingerprint)[:12], model=None,
                   config=dict(strategies=['immediate','capacity_aware'], strategy_options={}, model_id=None,
                               max_runtime_seconds=120, case_runtime_seconds=10)))
        write_json(folder/'state.json', dict(job_id=job_id, suite_id=suite['suite_id'], pid=os.getpid(),
                   status='starting', strategies=['immediate','capacity_aware'], implementation_id=digest(fingerprint)[:12],
                   total_rows=20, completed_rows=0))
        (self.service.root/'worker.lock').write_text(job_id)
        return job_id, folder

    def test_ten_unique_tests_and_real_ladder(self):
        self.assertEqual(len(TESTS), 10)
        self.assertEqual(len({r['id'] for r in TESTS}), 10)
        self.assertEqual(sum(t['kind']=='capacity' for t in TESTS), 4)
        self.assertEqual(fleet_ladder({'standard_fleet':3,'max_fleet':13}), [0,1,3,6,12,13])
        with self.assertRaises(ValueError): BenchmarkConfig(standard_fleet=100,max_fleet=1)
        with self.assertRaises(ValueError): BenchmarkConfig(seeds=[1,1])

    def test_integer_boundary_measured_without_discarding_higher_pass(self):
        attempts=[dict(fleet_size=n,status=s) for n,s in [(0,'passed'),(2,'failed'),(8,'passed'),(16,'failed')]]
        refine_capacity_boundary(attempts, lambda n:dict(fleet_size=n,status='passed' if n<=11 else 'failed'))
        self.assertEqual(max(a['fleet_size'] for a in attempts if a['status']=='passed'),11)
        self.assertIn(dict(fleet_size=12,status='failed'),attempts)
        self.assertIn(dict(fleet_size=2,status='failed'),attempts)

    def test_doubling_ladder_ignores_reference_and_non_power_ceiling(self):
        self.assertEqual(fleet_ladder(dict(search_mode='doubling',standard_fleet=3,max_fleet=13)),[0,2,4,8])
        self.assertEqual(fleet_ladder(dict(search_mode='doubling',standard_fleet=500,max_fleet=32768))[-1],32768)

    def test_unknown_boundary_remains_unknown(self):
        attempts=[dict(fleet_size=0,status='passed'),dict(fleet_size=10,status='failed')]
        refine_capacity_boundary(attempts, lambda n:dict(fleet_size=n,status='error'))
        self.assertEqual([a['status'] for a in attempts],['passed','error','failed'])

    def test_nested_sessions_and_individual_feasibility(self):
        short = session_pool(self.blocks, 41001, 3)
        long = session_pool(list(reversed(self.blocks)), 41001, 5)
        self.assertEqual(short, long[:3])
        for session in long:
            self.assertGreaterEqual((session['departure_step']-107)*.25*session['charger_kw']*session['efficiency'], session['energy_kwh'])
        district = short[0]['district_id']
        concentrated = session_pool(self.blocks,41001,5,district=district)
        self.assertEqual({s['district_id'] for s in concentrated}, {district})
        self.assertEqual({s['arrival_step'] for s in session_pool(self.blocks,41001,5,synchronized=True)}, {72})

    def test_frozen_suite_and_tamper_detection(self):
        a = self.suite(); b = self.suite()
        self.assertEqual(a, b)
        frozen = self.service.get_suite(a['suite_id'])
        self.assertAlmostEqual(frozen['demand']['worst'][72], 1.2*frozen['demand']['winter'][72])
        path = self.service.path('benchmark-suites',a['suite_id'])/'fixtures.json'
        frozen['pools']['city-41001'][0]['energy_kwh'] = 0
        write_json(path, frozen)
        with self.assertRaisesRegex(ValueError, 'changed'): self.service.get_suite(a['suite_id'])

    def test_grid_or_energy_failure_cannot_pass_or_gain_headroom_credit(self):
        good = trial_summary(measured(2))
        self.assertEqual(good['status'], 'passed')
        self.assertEqual(good['metrics']['min_stage_headroom_kw'], 48)
        self.assertEqual(good['metrics']['spare_stage_percent'], 48)
        self.assertEqual(trial_summary(measured(2,True))['status'],'failed')
        raw = measured(2); raw['intervals'][0]['converged'] = False
        result = trial_summary(raw)
        self.assertNotEqual(result['status'],'passed')
        self.assertIsNone(result['metrics']['min_stage_headroom_kw'])
        raw = measured(2); raw['intervals'][0]['violations'] = [{'kind':'undervoltage'}]
        self.assertEqual(trial_summary(raw)['status'],'failed')
        raw = measured(2); raw['intervals'].pop()
        self.assertEqual(trial_summary(raw)['status'],'incomplete')

    def test_all_seeds_required_and_worst_seed_metrics(self):
        a, b = trial_summary(measured(1)), trial_summary(measured(2,True))
        result = aggregate_trials([a,b])
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['metrics']['unmet_energy_kwh'],1.)
        self.assertEqual(result['metrics']['spare_stage_percent'],48.)
        self.assertEqual(aggregate_trials([a,dict(status='error',metrics={},reasons=['timeout'])])['status'],'incomplete')

    def test_nonmonotone_capacity_scan_common_fleet_and_shared_replays(self):
        suite = self.suite(); job_id, folder = self.prepared(suite)
        calls = []
        def simulate(options, profile, sessions, progress):
            calls.append((options['strategy'], len(sessions), digest(profile), digest(sessions)))
            return measured(len(sessions), fail=len(sessions)==2)
        with patch('mvgrid.novi_sad.playground.benchmark.simulate_case', side_effect=simulate):
            run_benchmark(self.temp.name, job_id)
        result = self.service.results(job_id)
        self.assertEqual(result['job']['status'],'completed')
        self.assertEqual(len(result['rows']),20)
        self.assertEqual(result['common_fleet'],1)
        for row in result['rows']:
            if row['kind']=='capacity':
                self.assertEqual(row['fleet_size'],4)
                self.assertEqual(row['status'],'ceiling_reached')
                self.assertEqual(row['first_failed_fleet'],2)
                self.assertEqual([a['fleet_size'] for a in row['attempts']], [0,1,2,4])
        a = {(count, demand, replay) for strategy,count,demand,replay in calls if strategy=='immediate'}
        b = {(count, demand, replay) for strategy,count,demand,replay in calls if strategy=='capacity_aware'}
        self.assertEqual(a,b)
        self.assertFalse((self.service.root/'worker.lock').exists())
        self.assertEqual(len(self.service.comparison(suite['suite_id'])['rows']),18)

    def test_errors_are_unknown_and_do_not_skip_peer(self):
        suite = self.suite(); job_id,_ = self.prepared(suite)
        def simulate(options, profile, sessions, progress):
            if options['strategy']=='immediate': raise RuntimeError('broken controller')
            return measured(len(sessions))
        with patch('mvgrid.novi_sad.playground.benchmark.simulate_case', side_effect=simulate): run_benchmark(self.temp.name, job_id)
        result = self.service.results(job_id)
        self.assertIsNone(result['common_fleet'])
        self.assertEqual(len(result['rows']),20)
        self.assertTrue(all(r['status']=='incomplete' for r in result['rows'] if r['strategy']=='immediate'))
        self.assertTrue(any(r['status']=='passed' for r in result['rows'] if r['strategy']=='capacity_aware'))

    def test_doubling_stops_at_first_failure_and_records_bracket(self):
        suite=self.service.create_suite(dict(name='Doubling',standard_fleet=2,max_fleet=2,seeds=[41001],search_mode='doubling',until_failure=True))
        job_id,_=self.prepared(suite)
        def simulate(options,profile,sessions,progress):
            return measured(len(sessions),fail=len(sessions)>=4)
        with patch('mvgrid.novi_sad.playground.benchmark.simulate_case',side_effect=simulate):
            run_benchmark(self.temp.name,job_id)
        result=self.service.results(job_id)
        self.assertEqual(result['job']['status'],'completed')
        for row in result['rows']:
            if row['kind']=='capacity':
                self.assertEqual(sorted(a['fleet_size'] for a in row['attempts']),[0,2,3,4])
                self.assertEqual(row['fleet_size'],3)
                self.assertEqual(row['first_failed_doubling'],4)
                self.assertEqual(row['next_failed_fleet'],4)

    def test_uncapped_sequence_continues_beyond_old_ceiling(self):
        from itertools import islice
        values=list(islice(capacity_counts(dict(config=dict(until_failure=True))),19))
        self.assertEqual(values[-3:],[65536,131072,262144])
        self.assertEqual(session_pool(self.blocks,41001,4)[:2],session_pool(self.blocks,41001,2))

    def test_cancellation_preserves_incomplete_and_releases_lock(self):
        suite = self.suite(); job_id,folder = self.prepared(suite)
        (folder/'cancel').touch()
        with patch('mvgrid.novi_sad.playground.benchmark.simulate_case') as simulate: run_benchmark(self.temp.name, job_id)
        simulate.assert_not_called()
        result = self.service.results(job_id)
        self.assertEqual(result['job']['status'],'cancelled')
        self.assertFalse(result['complete'])
        self.assertEqual(self.service.comparison(suite['suite_id'])['rows'],[])
        self.assertFalse((self.service.root/'worker.lock').exists())

    def test_unknown_strategy_and_missing_rl_model_rejected(self):
        suite = self.suite()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'registered'): self.service.start(suite['suite_id'], {'strategies':['does_not_exist']})
            with self.assertRaisesRegex(ValueError, 'frozen RL'): self.service.start(suite['suite_id'], {'strategies':['rl']})

    def test_frozen_rl_seed_leakage_rejected(self):
        from mvgrid.novi_sad.playground.rl import BinaryPolicy
        suite = self.suite()
        payload = dict(training_seeds=[41001], policy=BinaryPolicy().to_dict())
        model_id = 'model-'+digest(payload)[:20]
        write_json(self.service.path('models',model_id).with_suffix('.json'), dict(model_id=model_id,payload=payload))
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'overlap'): self.service.start(suite['suite_id'], dict(strategies=['rl'],model_id=model_id))

    def test_new_registered_algorithm_is_not_hardcoded_out(self):
        suite = self.suite()
        with patch.dict(os.environ, {}, clear=True), \
             patch('mvgrid.novi_sad.playground.benchmark.strategy_catalog', return_value=[dict(id='future_controller')]), \
             patch('mvgrid.novi_sad.playground.benchmark.subprocess.Popen') as spawn:
            spawn.return_value.pid = os.getpid()
            job = self.service.start(suite['suite_id'], dict(strategies=['future_controller']))
        self.assertEqual(job['total_rows'],10)
        request = read_json(self.service.path('benchmarks',job['job_id'])/'request.json')
        self.assertEqual(request['config']['strategies'],['future_controller'])

    def test_shared_worker_exclusion(self):
        suite = self.suite(); self.prepared(suite)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'worker is active'): self.service.start(suite['suite_id'],dict(strategies=['immediate']))

    def test_total_budget_never_publishes_complete(self):
        suite = self.suite(); job_id,folder = self.prepared(suite)
        request = read_json(folder/'request.json'); request['config']['max_runtime_seconds'] = -1
        write_json(folder/'request.json',request)
        with patch('mvgrid.novi_sad.playground.benchmark.simulate_case') as simulate: run_benchmark(self.temp.name,job_id)
        simulate.assert_not_called()
        result = self.service.results(job_id)
        self.assertEqual(result['job']['status'],'budget_exceeded')
        self.assertFalse(result['complete'])
        self.assertEqual(self.service.comparison(suite['suite_id'])['rows'],[])


if __name__ == '__main__': unittest.main()
