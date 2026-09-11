"""Independent bounded checks for continuous campaigns; no long training."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

from mvgrid.novi_sad.playground import continuous_campaign as campaign
from mvgrid.novi_sad.playground.service import digest, write_json, read_json


class CampaignSelectionAdversarialTests(unittest.TestCase):
    def test_target_is_optional_and_positive_probe_is_supported(self):
        self.assertIsNone(campaign.CampaignConfig().target_fleet)
        self.assertEqual(campaign.CampaignConfig(target_fleet=80000).target_fleet,80000)
        with self.assertRaises(ValueError):
            campaign.CampaignConfig(target_fleet=0)

    def test_unknown_baseline_evidence_cannot_become_capacity_improvement(self):
        policies=[dict(policy=name,status='completed',episodes=[dict(metrics=dict(complete=True,passed=True)) for _ in range(3)])
                  for name in ('candidate-0','replicate-1','replicate-2')]
        policies.extend(dict(policy=name,status='completed',episodes=[dict(status='incomplete',
            complete=False,metrics={'nonconverged_steps':1}) for _ in range(3)]) for name in campaign.BASELINES)
        report={'evaluation':[dict(block_id='normal-10',family='normal',fleet_size=10,complete=True,policies=policies)]}
        self.assertNotEqual(campaign.summarize_evaluation(report)['verdict'],'tested_capacity_improvement')

    def test_real_evaluation_shape_is_eligible_and_unmet_is_ranked(self):
        good = {'seed':0, 'reward':1., 'steps':132, 'metrics':dict(
            complete=True, passed=True, unmet_energy_kwh=0., violation_intervals=0, peak_demand_kw=100.)}
        bad = copy.deepcopy(good)
        bad['metrics'].update(passed=False, unmet_energy_kwh=10.)
        self.assertIsNotNone(campaign._score([good]))
        self.assertLess(campaign._score([good]), campaign._score([bad]))

    def test_invalid_or_partial_evidence_cannot_be_scored(self):
        for rows in ([], [{'metrics':{'complete':False,'passed':True}}],
                     [{'metrics':{'complete':False,'numerical_invalid':True}}]):
            with self.subTest(rows=rows):
                self.assertIsNone(campaign._score(rows))

    def test_grid_violations_affect_candidate_order(self):
        one = dict(complete=True,passed=False,unmet_energy_kwh=0.,violation_intervals=1,peak_demand_kw=100.)
        two = {**one,'violation_intervals':2}
        self.assertLess(campaign._score([{'metrics':one}]), campaign._score([{'metrics':two}]))

    def test_source_binding_covers_replay_and_controller_dependencies(self):
        binding = campaign.runtime_binding()
        for name in ('benchmark.py','smoothed_llf.py','valley_odc.py'):
            self.assertIn(name, binding['source'])

    def test_seed_ranges_cannot_overlap_or_reuse_benchmark_seed(self):
        for changes in ({'validation_seed_base':100001}, {'training_seed_base':0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                campaign.CampaignConfig.model_validate(changes)


class ComparativeEvidenceAdversarialTests(unittest.TestCase):
    def rows(self, passed=True, peak=100.):
        return [dict(family='normal',fleet_size=100,seed=300000+i,demand_hash='d',replay_hash=str(i),
            status='passed' if passed else 'failed',complete=True,metrics=dict(requested_energy_kwh=10.,
            peak_demand_kw=peak,unmet_energy_kwh=0. if passed else 1.,numerical_invalid=False)) for i in range(3)]

    def report(self):
        policies=[dict(policy=name,status='completed',episodes=self.rows(peak=90.))
                  for name in ('candidate-0','replicate-1','replicate-2')]
        policies += [dict(policy=name,status='completed',episodes=self.rows()) for name in campaign.BASELINES]
        return {'evaluation':[dict(family='normal',fleet_size=100,complete=True,policies=policies)]}

    def test_peak_win_requires_matched_complete_service(self):
        baseline=self.rows()
        result=campaign.compare_validation(self.rows(peak=90.),{'capacity_aware':baseline})['capacity_aware']
        self.assertTrue(result['complete_valid'])
        self.assertEqual(result['feasible_peak_deltas_kw'],[-10.]*3)
        result=campaign.compare_validation(self.rows(passed=False,peak=0.),{'capacity_aware':baseline})['capacity_aware']
        self.assertEqual(result['feasibility_regressions'],3)
        self.assertEqual(result['feasible_peak_deltas_kw'],[])

    def test_hash_unknown_duplicate_and_service_mismatch_are_inconclusive(self):
        for mutate in (lambda r:r[0].update(replay_hash='changed'),
                       lambda r:r[0].update(status='unknown'),
                       lambda r:r.append(copy.deepcopy(r[0])),
                       lambda r:r[0]['metrics'].update(requested_energy_kwh=11.)):
            baseline=self.rows(); mutate(baseline)
            result=campaign.compare_validation(self.rows(),{'capacity_aware':baseline})['capacity_aware']
            self.assertFalse(result['complete_valid'])
            self.assertIsNone(result['feasibility_wins'])
            self.assertEqual(result['feasible_peak_deltas_kw'],[])

    def test_flat_numerical_invalid_cannot_support_win(self):
        baseline=self.rows(); baseline[0]['metrics']['numerical_invalid']=True
        result=campaign.compare_validation(self.rows(peak=90.),{'capacity_aware':baseline})['capacity_aware']
        self.assertFalse(result['complete_valid'])

    def test_missing_energy_is_unknown_not_exception_or_win(self):
        baseline=self.rows(); baseline[0]['metrics'].pop('requested_energy_kwh')
        result=campaign.compare_validation(self.rows(),{'capacity_aware':baseline})['capacity_aware']
        self.assertFalse(result['complete_valid'])

    def test_summary_requires_every_baseline_and_matching_hashes(self):
        for change in ('missing','hash'):
            report=self.report()
            if change=='missing': report['evaluation'][0]['policies'].pop()
            else: report['evaluation'][0]['policies'][-1]['episodes'][0]['demand_hash']='other'
            summary=campaign.summarize_evaluation(report)
            self.assertFalse(summary['complete_valid_comparison'])
            self.assertEqual(summary['verdict'],'inconclusive')

    def test_matched_peak_improvement_is_distinct_from_capacity(self):
        summary=campaign.summarize_evaluation(self.report())
        self.assertTrue(summary['complete_valid_comparison'])
        self.assertEqual(summary['verdict'],'no_consistent_capacity_improvement')
        self.assertTrue(all(e['peak_improved_without_regression'] for e in summary['feasible_peak_evidence'].values()))


class FrozenFactoryAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder/'network.json').write_text('frozen network',encoding='utf-8')
        import hashlib
        self.fixture = dict(config={'district':'D'}, demand={'normal':[100.]*132},
            blocks=[{'id':'node'}], limits={'max_loading_percent':100.}, districts=[], network_capacity={})
        self.request = dict(config=campaign.CampaignConfig().model_dump(), anchors={'normal':{'fleet_size':100}},
            horizon_steps=132, fixture_hash=digest(self.fixture),
            network_hash=hashlib.sha256((self.folder/'network.json').read_bytes()).hexdigest())
        write_json(self.folder/'fixtures.json', self.fixture)
        write_json(self.folder/'request.json', self.request)

    def test_split_seeds_and_full_frozen_horizon(self):
        def sessions(blocks, seed, count, district, synchronized, charging_profile='home_only'):
            self.assertEqual(charging_profile, 'home_only')
            return [dict(id=str(i),seed=seed,departure_step=132) for i in range(count)]
        with patch('mvgrid.novi_sad.playground.benchmark.session_pool',side_effect=sessions), \
             patch('mvgrid.novi_sad.playground.demand.allocate_block_demand',return_value={'node':[100.]*132}):
            rows = [campaign.FrozenEpisodeFactory(self.folder,split,('normal',2))(7)
                    for split in ('train','validation','test')]
            self.assertEqual([r['metadata']['seed'] for r in rows],[100007,200007,300007])
            for row in rows:
                self.assertEqual(row['demand_kw'],[100.]*132)
                self.assertEqual(row['case']['block_demand_kw'],{'node':[100.]*132})
                self.assertFalse(row['case']['stop_on_violation'])
            self.assertEqual(len({r['metadata']['replay_hash'] for r in rows}),3)

    def test_normal_stress_training_reaches_target_and_five_percent_above(self):
        self.request['config']['target_fleet']=80000
        write_json(self.folder/'request.json',self.request)
        from unittest.mock import Mock
        for fraction,count in ((1.,80000),(1.05,84000)):
            rng=Mock()
            rng.integers.return_value=0
            rng.choice.side_effect=[2,fraction]
            with self.subTest(fraction=fraction), \
                 patch.object(campaign.np.random,'default_rng',return_value=rng), \
                 patch('mvgrid.novi_sad.playground.benchmark.session_pool',return_value=[]) as pool, \
                 patch('mvgrid.novi_sad.playground.demand.allocate_block_demand',return_value={'node':[100.]*132}):
                episode=campaign.FrozenEpisodeFactory(self.folder,'train')(3)
            self.assertEqual(episode['metadata']['fleet_size'],count)
            self.assertEqual(pool.call_args.args[2],count)

    def test_default_stress_uses_strongest_comparison_bound_without_target(self):
        from unittest.mock import Mock
        self.request['comparison_anchors']={'normal':{'fleet_size':140}}
        write_json(self.folder/'request.json',self.request)
        rng=Mock(); rng.integers.return_value=0; rng.choice.side_effect=[2,1.05]
        with patch.object(campaign.np.random,'default_rng',return_value=rng), \
             patch('mvgrid.novi_sad.playground.benchmark.session_pool',return_value=[]), \
             patch('mvgrid.novi_sad.playground.demand.allocate_block_demand',return_value={'node':[100.]*132}):
            episode=campaign.FrozenEpisodeFactory(self.folder,'train')(3)
        self.assertEqual(episode['metadata']['fleet_size'],147)

    def test_held_out_grid_contains_target_and_original_stronger_counts(self):
        import time
        request=dict(config=campaign.CampaignConfig(target_fleet=80000).model_dump(),binding={},
            anchors={'normal':{'fleet_size':60311},'worst':{'fleet_size':24126}},
            comparison_anchors={'normal':{'fleet_size':65544},'worst':{'fleet_size':26000}})
        def factory(folder,split,fixed):
            family,count=fixed
            return lambda seed:dict(case={},demand_kw=[],sessions=[],metadata=dict(family=family,fleet_size=count,seed=seed))
        report={'evaluation':[]}
        with patch.object(campaign,'FrozenEpisodeFactory',side_effect=factory), \
             patch('mvgrid.novi_sad.playground.continuous_ppo.evaluate_policy',return_value=dict(status='completed',episodes=[{}]*3)), \
             patch('mvgrid.novi_sad.playground.simulation.simulate_case',return_value={}), \
             patch('mvgrid.novi_sad.playground.benchmark.trial_summary',return_value=dict(status='passed',complete=True,metrics={})):
            campaign.evaluate_campaign(self.folder,request,[{'key':'candidate-0','checkpoint':'fixture'}],
                                       report,time.monotonic()+10,lambda:None,lambda:None)
        normal={b['fleet_size'] for b in report['evaluation'] if b['family']=='normal'}
        worst={b['fleet_size'] for b in report['evaluation'] if b['family']=='worst'}
        self.assertTrue({80000,84000,65544,round(65544*1.05)}<=normal)
        self.assertNotIn(80000,worst)

    def test_mutated_fixture_is_rejected(self):
        self.fixture['demand']['normal'][0] = 999.
        write_json(self.folder/'fixtures.json', self.fixture)
        with self.assertRaises(ValueError):
            campaign.FrozenEpisodeFactory(self.folder)

    def test_original_anchor_seed_options_and_failure_gate_precede_training(self):
        import time
        self.fixture['config']['seeds']=[41001]
        replay=[dict(id=str(i),seed=41001,departure_step=132) for i in range(2)]
        self.request.update(fixture_hash=digest(self.fixture),benchmark_strategy_options={'forecast':'previous_day'},
            anchors={'normal':dict(fleet_size=2,strategy='capacity_aware',evidence={'trials':[dict(
                seed=41001,demand_hash=digest([100.]*132),replay_hash=digest(replay))]})})
        write_json(self.folder/'fixtures.json',self.fixture)
        write_json(self.folder/'request.json',self.request)
        calls=[]
        def simulate(case,demand,sessions,progress):
            calls.append((case,demand,sessions))
            return dict(status='failed' if sessions else 'passed',metrics={})
        with patch('mvgrid.novi_sad.playground.benchmark.session_pool',side_effect=lambda b,s,n,d,y,p='home_only':replay[:n]), \
             patch('mvgrid.novi_sad.playground.demand.allocate_block_demand',return_value={'node':[100.]*132}), \
             patch('mvgrid.novi_sad.playground.simulation.simulate_case',side_effect=simulate), \
             patch('mvgrid.novi_sad.playground.benchmark.trial_summary',side_effect=lambda result:result), \
             patch('mvgrid.novi_sad.playground.continuous_ppo.train_policy') as train:
            with self.assertRaisesRegex(ValueError,'anchor replay failed'):
                campaign.preflight_and_pilot(self.folder,self.request,time.monotonic()+10,lambda:None)
        self.assertFalse(train.called)
        self.assertEqual(len(calls),2)
        for case,demand,sessions in calls:
            self.assertEqual(case['seed'],41001)
            self.assertEqual(case['strategy_options'],{'forecast':'previous_day'})
            self.assertEqual(len(demand),132)
        self.assertEqual(calls[1][2],replay)


class RewardAdversarialTests(unittest.TestCase):
    def test_zero_charging_does_not_beat_feasible_service_or_pass(self):
        from test_continuous_env import TinySimulator, NODES, factory
        from mvgrid.novi_sad.playground.continuous_env import ContinuousEVEnv
        class CompatibleTinySimulator(TinySimulator):
            def measure_baseline_voltages(self):
                return {node:1. for node in NODES}
            def reset(self, case, demand, sessions, on_baseline_step=None):
                if on_baseline_step:
                    on_baseline_step({})
                super().reset(case,demand,sessions)
                import pandas as pd
                class Net(dict):
                    pass
                self.net=Net()
                self.net.res_bus=pd.DataFrame({'vm_pu':[1.]*52})
                for i,block in enumerate(self.blocks):
                    block['bus_index']=i
        with patch('mvgrid.novi_sad.playground.continuous_env.Simulator',CompatibleTinySimulator):
            zero = ContinuousEVEnv(factory,NODES)
            full = ContinuousEVEnv(factory,NODES)
            zero.reset(seed=7); full.reset(seed=7)
            for _ in range(4):
                zero.step(-np.ones(52)); full.step(np.ones(52))
            self.assertFalse(zero.episode_metrics['passed'])
            self.assertTrue(full.episode_metrics['passed'])
            self.assertGreater(full.reward_total,zero.reward_total)
            self.assertEqual(zero.episode_metrics['unmet_energy_kwh'],1.)


class CampaignLifecycleAdversarialTests(unittest.TestCase):
    def test_dead_worker_elapsed_budget_is_conservatively_recovered(self):
        with tempfile.TemporaryDirectory() as root:
            service=campaign.ContinuousCampaignService(root)
            identifier='ppo-'+'c'*20
            write_json(service.folder(identifier)/'state.json',dict(campaign_id=identifier,status='running',
                pid=999999,elapsed_seconds=50.,last_active_wall_time=1000.))
            with patch('psutil.pid_exists',return_value=False), patch.object(campaign.time,'time',return_value=2000.):
                recovered=service.get(identifier)
                self.assertEqual(recovered['status'],'interrupted')
                self.assertEqual(recovered['elapsed_seconds'],1050.)
                self.assertEqual(service.get(identifier)['elapsed_seconds'],1050.)

    def test_pilot_retry_uses_its_committed_checkpoint(self):
        import time
        with tempfile.TemporaryDirectory() as root:
            pointer=Path(root)/'pilot-1/latest.json'
            write_json(pointer,{'checkpoint':'existing-update'})
            with patch.object(campaign,'replay_benchmark_anchors',return_value=[]), \
                 patch.object(campaign,'FrozenEpisodeFactory'), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo._manifest',return_value={'timesteps':1024}), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo.train_policy',return_value={'status':'completed'}) as train:
                campaign.preflight_and_pilot(Path(root),{'binding':{}},time.monotonic()+10,lambda:None)
            self.assertEqual(Path(train.call_args_list[0].kwargs['resume_from']),pointer)
            self.assertEqual(train.call_args_list[0].args[2],2048)

    def test_completed_pilot_reuses_measured_timing_not_checkpoint_load_time(self):
        import time
        with tempfile.TemporaryDirectory() as root:
            for workers,seconds in ((1,100.),(2,200.)):
                write_json(Path(root)/f'pilot-{workers}'/'timing.json',dict(seconds=seconds,measured_transitions=1024))
            with patch.object(campaign,'replay_benchmark_anchors',return_value=[]), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo.train_policy') as train:
                result=campaign.preflight_and_pilot(Path(root),{'binding':{}},time.monotonic()+10,lambda:None)
            self.assertFalse(train.called)
            self.assertEqual(result['budget_update_seconds'],125.)

    def test_partial_validation_cannot_select_a_policy_or_complete_campaign(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            service=campaign.ContinuousCampaignService(root)
            identifier='ppo-'+'b'*20
            folder=service.folder(identifier)
            request=dict(config=campaign.CampaignConfig(budget_hours=1).model_dump(),binding={},
                         anchors={'normal':{'fleet_size':100}})
            write_json(folder/'request.json',request)
            write_json(folder/'state.json',dict(campaign_id=identifier,status='queued',pid=os.getpid()))
            partial={'status':'budget_exhausted','episodes':[dict(seed=0,metrics=dict(
                complete=True,passed=True,unmet_energy_kwh=0.,violation_intervals=0,peak_demand_kw=100.))]}
            with patch.object(campaign,'runtime_binding',return_value={}), \
                 patch.object(campaign,'_acquire_worker'), \
                 patch.object(campaign,'FrozenEpisodeFactory'), \
                 patch.object(campaign,'preflight_and_pilot',return_value=dict(n_envs=1,budget_update_seconds=1.,preflight=[])), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo.train_policy',return_value=dict(status='completed',checkpoint='fixture')), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo.evaluate_policy',return_value=partial), \
                 patch.object(campaign,'evaluate_campaign') as held_out:
                campaign.run_campaign(root,identifier)
            self.assertNotEqual(read_json(folder/'state.json')['status'],'completed')
            self.assertFalse(held_out.called)

    def test_missing_validation_baselines_cannot_select_policy(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            service=campaign.ContinuousCampaignService(root)
            identifier='ppo-'+'b'*20
            folder=service.folder(identifier)
            request=dict(config=campaign.CampaignConfig(budget_hours=1).model_dump(),binding={},
                         anchors={'normal':{'fleet_size':100}})
            write_json(folder/'request.json',request)
            write_json(folder/'state.json',dict(campaign_id=identifier,status='queued',pid=os.getpid()))
            partial={'status':'completed','episodes':[dict(seed=0,metrics=dict(
                complete=True,passed=True,unmet_energy_kwh=0.,violation_intervals=0,peak_demand_kw=100.))]*2}
            with patch.object(campaign,'runtime_binding',return_value={}), \
                 patch.object(campaign,'_acquire_worker'), \
                 patch.object(campaign,'FrozenEpisodeFactory'), \
                 patch.object(campaign,'preflight_and_pilot',return_value=dict(n_envs=1,budget_update_seconds=1.,preflight=[])), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo.train_policy',return_value=dict(status='completed',checkpoint='fixture')), \
                 patch('mvgrid.novi_sad.playground.continuous_ppo.evaluate_policy',return_value=partial), \
                 patch.object(campaign,'validation_baselines',return_value={}), \
                 patch.object(campaign,'evaluate_campaign') as held_out:
                campaign.run_campaign(root,identifier)
            self.assertNotEqual(read_json(folder/'state.json')['status'],'completed')
            self.assertFalse(held_out.called)
            self.assertIn('validation',read_json(folder/'state.json').get('error','').lower())

    def test_failed_spawn_does_not_leave_permanent_queued_campaign(self):
        with tempfile.TemporaryDirectory() as root:
            service = campaign.ContinuousCampaignService(root)
            identifier = 'ppo-'+'a'*20
            folder = service.folder(identifier)
            write_json(folder/'state.json',dict(campaign_id=identifier,status='prepared',pid=None))
            write_json(folder/'request.json',{'binding':{}})
            with patch.object(campaign,'runtime_binding',return_value={}), \
                 patch.object(campaign.subprocess,'Popen',side_effect=OSError('launch failed')):
                with self.assertRaises(OSError):
                    service.start(identifier)
            self.assertNotIn(service.get(identifier)['status'],campaign.ACTIVE)

    def test_same_directory_checkpoint_resume_advances_without_overwrite(self):
        from test_continuous_ppo import TinyEnv
        from mvgrid.novi_sad.playground.continuous_ppo import train_policy
        with tempfile.TemporaryDirectory() as root, \
             patch('mvgrid.novi_sad.playground.continuous_env.ContinuousEVEnv',TinyEnv):
            options=dict(seed=7,rollout_steps=8,batch_size=8,n_epochs=1,binding={'fixture':'same'})
            first=train_policy(None,root,8,**options)
            first_bytes=(Path(first['checkpoint'])/'model.zip').read_bytes()
            pointer=Path(root)/'latest.json'
            self.assertTrue(pointer.exists())
            second=train_policy(None,root,16,resume_from=pointer,**options)
            self.assertEqual(second['timesteps'],16)
            self.assertEqual(second['completed_updates'],2)
            self.assertNotEqual(first['checkpoint'],second['checkpoint'])
            self.assertEqual((Path(first['checkpoint'])/'model.zip').read_bytes(),first_bytes)


if __name__=='__main__':
    unittest.main()
