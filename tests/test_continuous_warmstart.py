"""Bounded warm-start interruption and budgeting regressions; no grid training."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mvgrid.novi_sad.playground import continuous_campaign as campaign
from mvgrid.novi_sad.playground import continuous_ppo as ppo
from mvgrid.novi_sad.playground.service import read_json, write_json
import test_continuous_ppo as fixtures


class WarmStartStopTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ContinuousPPOTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        class Stop(InterruptedError):
            def __init__(self, reason):
                self.stop_reason = reason
                super().__init__(reason)
        self.Stop = Stop
        self.fixture.module.ContinuousStop = Stop

    def test_collection_and_fitting_interrupts_return_no_fake_checkpoint(self):
        for phase in ('collection','fitting'):
            for reason in ('cancelled','budget_exhausted'):
                with self.subTest(phase=phase,reason=reason), \
                     patch.object(ppo,'collect_llf_demonstrations',side_effect=self.Stop(reason) if phase=='collection' else None,return_value=Path('unused')), \
                     patch.object(ppo,'initialize_from_demonstrations',side_effect=self.Stop(reason) if phase=='fitting' else None):
                    result=self.fixture.train(phase+reason,8,llf_warmstart_episodes=1)
                self.assertEqual(result['status'],reason)
                self.assertEqual(result['timesteps'],0)
                self.assertEqual(result['completed_updates'],0)
                self.assertEqual(result['episodes'],[])
                self.assertIsNone(result['checkpoint'])
                self.assertGreaterEqual(result['initialization_timing'][phase+'_seconds'],0.)

    def test_expired_budget_never_collects_demonstrations(self):
        with patch.object(ppo,'collect_llf_demonstrations') as collect:
            result=self.fixture.train('expired-warm',8,llf_warmstart_episodes=1,deadline=0)
        self.assertEqual(result['status'],'budget_exhausted')
        collect.assert_not_called()

    def test_real_initialization_resume_matches_uninterrupted_policy(self):
        import numpy as np
        import torch
        import stable_baselines3 as sb3
        data=self.fixture.root/'demonstrations.npz'
        np.savez(data,observations=np.array([[0.,0.,1.],[.1,.2,1.]],dtype=np.float32),
                 actions=np.array([[.2],[.1]],dtype=np.float32),masks=np.ones((2,1),dtype=bool))
        options=dict(llf_warmstart_episodes=1,llf_warmstart_epochs=2,normalize_reward=True)
        with patch.object(ppo,'collect_llf_demonstrations',return_value=data) as collect:
            full=self.fixture.train('full-warm',32,**options)
            partial=self.fixture.train('partial-warm',16,**options)
            resumed=self.fixture.train('resume-warm',32,resume_from=partial['checkpoint'],**options)
        self.assertEqual(collect.call_count,2)
        self.assertEqual(full['episodes'],resumed['episodes'])
        a,b=[sb3.PPO.load(Path(row['checkpoint'])/'model.zip',device='cpu') for row in (full,resumed)]
        for key,value in a.policy.state_dict().items():
            self.assertTrue(torch.equal(value,b.policy.state_dict()[key]),key)
        self.assertEqual(resumed['initialization_timing'],dict(collection_seconds=0.,fitting_seconds=0.))
        self.assertGreater(read_json(self.fixture.root/'partial-warm'/'initialization.json')['timing']['fitting_seconds'],0.)


class WarmStartBudgetTests(unittest.TestCase):
    def test_pilot_separates_collection_fitting_and_ppo_time(self):
        with tempfile.TemporaryDirectory() as folder:
            request={'binding':{},'config':dict(llf_warmstart_episodes=2,llf_warmstart_epochs=3)}
            results=[dict(status='completed',initialization_timing=dict(collection_seconds=20.,fitting_seconds=10.)),
                     dict(status='completed',initialization_timing=dict(collection_seconds=0.,fitting_seconds=20.))]
            with patch.object(campaign,'replay_benchmark_anchors',return_value=[]), \
                 patch.object(campaign,'FrozenEpisodeFactory'), \
                 patch.object(campaign.time,'monotonic',side_effect=[0.,100.,200.,250.]), \
                 patch.object(ppo,'train_policy',side_effect=results) as train:
                result=campaign.preflight_and_pilot(Path(folder),request,10000,lambda:None)
            self.assertEqual(result['n_envs'],2)
            self.assertEqual(result['budget_update_seconds'],37.5)
            self.assertEqual(result['budget_initialization_seconds'],25.)
            self.assertEqual(read_json(Path(folder)/'pilot-1'/'timing.json')['collection_seconds'],20.)
            for call in train.call_args_list:
                self.assertEqual(call.kwargs['llf_warmstart_episodes'],2)
                self.assertEqual(call.kwargs['llf_warmstart_epochs'],3)
            with patch.object(campaign,'replay_benchmark_anchors',return_value=[]),patch.object(ppo,'train_policy') as train:
                cached=campaign.preflight_and_pilot(Path(folder),request,10000,lambda:None)
            train.assert_not_called()
            self.assertEqual(result,cached)

    def test_pilot_retry_preserves_fitting_measurement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for workers in (1,2):
                write_json(root/f'pilot-{workers}'/'latest.json',{'checkpoint':'existing'})
                write_json(root/f'pilot-{workers}'/'initialization.json',{'timing':{'fitting_seconds':30.}})
            with patch.object(campaign,'replay_benchmark_anchors',return_value=[]), \
                 patch.object(campaign,'FrozenEpisodeFactory'), \
                 patch.object(ppo,'_manifest',return_value={'timesteps':1024}), \
                 patch.object(ppo,'train_policy',return_value=dict(status='completed',initialization_timing=dict(collection_seconds=0.,fitting_seconds=0.))):
                result=campaign.preflight_and_pilot(root,{'binding':{},'config':{'llf_warmstart_episodes':2}},10000,lambda:None)
            self.assertEqual(result['budget_initialization_seconds'],37.5)

    def test_pilot_stop_reason_is_preserved(self):
        for status,exception in (('cancelled',InterruptedError),('budget_exhausted',TimeoutError)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as folder, \
                 patch.object(campaign,'replay_benchmark_anchors',return_value=[]), \
                 patch.object(campaign,'FrozenEpisodeFactory'), \
                 patch.object(ppo,'train_policy',return_value={'status':status}):
                with self.assertRaises(exception):
                    campaign.preflight_and_pilot(Path(folder),{'binding':{}},10000,lambda:None)

    def test_campaign_reduces_updates_and_preserves_training_stop(self):
        for stop,expected in (('cancelled','cancelled'),('budget_exhausted','budget_exceeded')):
            with self.subTest(stop=stop),tempfile.TemporaryDirectory() as root:
                service=campaign.ContinuousCampaignService(root)
                identifier='ppo-'+'e'*20; folder=service.folder(identifier)
                cfg=campaign.CampaignConfig(budget_hours=1).model_dump()
                cfg['llf_warmstart_episodes']=2
                write_json(folder/'request.json',dict(config=cfg,binding={},anchors={'normal':{'fleet_size':100}}))
                write_json(folder/'state.json',dict(campaign_id=identifier,status='queued',pid=os.getpid()))
                with patch.object(campaign,'runtime_binding',return_value={}), \
                     patch.object(campaign,'_acquire_worker'), \
                     patch.object(campaign,'FrozenEpisodeFactory'), \
                     patch.object(campaign,'preflight_and_pilot',return_value=dict(n_envs=1,budget_update_seconds=10.,budget_initialization_seconds=100.,preflight=[])), \
                     patch.object(ppo,'train_policy',return_value=dict(status=stop,checkpoint=None,timesteps=0)) as train:
                    campaign.run_campaign(root,identifier)
                self.assertEqual(read_json(folder/'state.json')['status'],expected)
                self.assertEqual(train.call_count,1)
                self.assertEqual(train.call_args.args[2],33*1024)
                self.assertEqual(read_json(folder/'report.json')['trials'][0]['status'],stop)

    def test_unaffordable_initialization_or_explicit_updates_prevent_launch(self):
        for fitting,steps in ((500.,None),(100.,40000)):
            with self.subTest(fitting=fitting,steps=steps),tempfile.TemporaryDirectory() as root:
                service=campaign.ContinuousCampaignService(root)
                identifier='ppo-'+'f'*20; folder=service.folder(identifier)
                cfg=campaign.CampaignConfig(budget_hours=1).model_dump()
                cfg.update(training_timesteps=steps,llf_warmstart_episodes=2)
                write_json(folder/'request.json',dict(config=cfg,binding={},anchors={'normal':{'fleet_size':100}}))
                write_json(folder/'state.json',dict(campaign_id=identifier,status='queued',pid=os.getpid()))
                with patch.object(campaign,'runtime_binding',return_value={}), \
                     patch.object(campaign,'_acquire_worker'), \
                     patch.object(campaign,'preflight_and_pilot',return_value=dict(n_envs=1,budget_update_seconds=10.,budget_initialization_seconds=fitting,preflight=[])), \
                     patch.object(ppo,'train_policy') as train:
                    campaign.run_campaign(root,identifier)
                train.assert_not_called()
                self.assertEqual(read_json(folder/'state.json')['status'],'insufficient_throughput')


if __name__=='__main__':
    unittest.main()
