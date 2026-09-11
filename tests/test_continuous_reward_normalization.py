"""Grid reward scaling changes learning feedback, never electrical acceptance."""
import json
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from mvgrid.novi_sad.playground import continuous_env as envmod
from mvgrid.novi_sad.playground import continuous_ppo as ppo
from mvgrid.novi_sad.playground import continuous_campaign as campaign
from mvgrid.novi_sad.playground.service import write_json
import test_continuous_env as envfixtures
import test_continuous_ppo as ppofixtures
import test_continuous_rl_adversarial as frozenfixtures


class GridRewardNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.patcher=patch.object(envmod,'Simulator',envfixtures.TinySimulator)
        self.patcher.start();self.addCleanup(self.patcher.stop)

    def make(self,mode='none',steps=4):
        def factory(seed):
            fixture=envfixtures.factory(seed)
            fixture['demand_kw']=[52.]*steps
            fixture['sessions'][0]['departure_step']=steps
            fixture['case']['violations']=[dict(kind='undervoltage',asset_type='bus',asset_id='b',value=.9,limit=.95)]
            return fixture
        factory.grid_penalty_normalization=mode
        return envmod.ContinuousEVEnv(factory,envfixtures.NODES)

    def test_integrated_penalty_and_physical_acceptance(self):
        severity=1+.05/.95
        for steps in (4,8):
            legacy,normalized=self.make(steps=steps),self.make('episode_horizon',steps)
            legacy.reset(seed=7);normalized.reset(seed=7)
            for _ in range(steps):
                a=legacy.step(np.ones(52));b=normalized.step(np.ones(52))
                self.assertEqual(a[2:4],b[2:4])
                self.assertEqual(a[4]['continuous']['executed_node_kw'],b[4]['continuous']['executed_node_kw'])
            self.assertAlmostEqual(legacy.episode_metrics['reward_components']['grid'],-20*severity*steps)
            self.assertAlmostEqual(normalized.episode_metrics['reward_components']['grid'],-20*severity)
            for key in ('passed','complete','unmet_energy_kwh','delivered_energy_kwh','violation_intervals','peak_demand_kw'):
                self.assertEqual(legacy.episode_metrics[key],normalized.episode_metrics[key])
            self.assertFalse(normalized.episode_metrics['passed'])
            self.assertEqual(normalized.episode_metrics['reward_config']['grid_penalty_divisor'],steps)
            self.assertIn('/episode_horizon_steps',normalized.episode_metrics['reward_formula'])

    def test_truncation_does_not_shrink_reward_denominator(self):
        env=self.make('episode_horizon',8);env.reset(seed=7,options={'max_steps':1})
        result=env.step(np.ones(52))
        self.assertTrue(result[3]);self.assertEqual(result[4]['continuous']['grid_penalty_divisor'],8)
        self.assertFalse(env.episode_metrics['passed'])

    def test_snapshot_preserves_scaling_and_rejects_mode_change(self):
        env=self.make('episode_horizon');env.reset(seed=7);env.step(np.ones(52));state=env.get_state()
        other=self.make('episode_horizon');other.set_state(state)
        a,b=env.step(np.zeros(52)),other.step(np.zeros(52))
        self.assertEqual(a[1],b[1]);self.assertEqual(a[4]['continuous'],b[4]['continuous'])
        with self.assertRaisesRegex(ValueError,'reward configuration'):
            self.make().set_state(state)
        legacy=self.make();legacy.reset(seed=7);old=legacy.get_state();old.pop('grid_penalty_normalization')
        restored=self.make();restored.set_state(old)
        self.assertEqual(restored.grid_penalty_divisor,1)

    def test_default_and_invalid_config(self):
        self.assertEqual(campaign.CampaignConfig().grid_penalty_normalization,'none')
        with self.assertRaises(ValueError):campaign.CampaignConfig(grid_penalty_normalization='silently_ignore')
        env=envmod.ContinuousEVEnv(envfixtures.factory,envfixtures.NODES);env.reset(seed=7)
        self.assertEqual(env.grid_penalty_divisor,1)

    def test_frozen_factory_forwards_mode_without_changing_physical_inputs(self):
        fixture=frozenfixtures.FrozenFactoryAdversarialTests();fixture.setUp()
        try:
            with patch('mvgrid.novi_sad.playground.benchmark.session_pool',return_value=[]), \
                 patch('mvgrid.novi_sad.playground.demand.allocate_block_demand',return_value={'node':[100.]*132}):
                old=campaign.FrozenEpisodeFactory(fixture.folder,'validation',('normal',2))(7)
                fixture.request['config']['grid_penalty_normalization']='episode_horizon'
                write_json(fixture.folder/'request.json',fixture.request)
                factory=campaign.FrozenEpisodeFactory(fixture.folder,'validation',('normal',2));new=factory(7)
            self.assertEqual(factory.grid_penalty_normalization,'episode_horizon')
            self.assertEqual(new['reward_config'],{'grid_penalty_normalization':'episode_horizon'})
            for key in ('case','demand_kw','sessions','metadata'):self.assertEqual(old[key],new[key])
        finally:fixture.doCleanups()


class GridRewardCheckpointTests(unittest.TestCase):
    def test_checkpoint_resume_and_evaluation_enforce_mode_legacy_default(self):
        fixture=ppofixtures.ContinuousPPOTests();fixture.setUp()
        try:
            options=dict(seed=13,rollout_steps=8,batch_size=8,n_epochs=1,binding={})
            factory=SimpleNamespace(grid_penalty_normalization='episode_horizon')
            result=ppo.train_policy(factory,fixture.root/'normalized',8,**options)
            manifest=json.loads((Path(result['checkpoint'])/'manifest.json').read_text())
            self.assertEqual(manifest['config']['grid_penalty_normalization'],'episode_horizon')
            with self.assertRaisesRegex(ValueError,'configuration'):
                ppo.train_policy(None,fixture.root/'wrong',16,resume_from=result['checkpoint'],**options)
            with self.assertRaisesRegex(ValueError,'reward configuration'):
                ppo.evaluate_policy(result['checkpoint'],None,[7],binding={})
            self.assertEqual(ppo.evaluate_policy(result['checkpoint'],factory,[7],binding={})['status'],'completed')
            resumed=ppo.train_policy(factory,fixture.root/'resumed',16,resume_from=result['checkpoint'],**options)
            self.assertEqual(resumed['timesteps'],16)
            legacy=ppo.train_policy(None,fixture.root/'legacy',8,**options)
            path=Path(legacy['checkpoint'])/'manifest.json'
            manifest=json.loads(path.read_text());manifest['config'].pop('grid_penalty_normalization');path.write_text(json.dumps(manifest))
            old=ppo.train_policy(None,fixture.root/'legacy-resumed',16,resume_from=legacy['checkpoint'],**options)
            self.assertEqual(old['timesteps'],16)
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
