"""Actual SB3 learning checks on a tiny deterministic Gym task; no grid/CLI calls."""
import copy
from pathlib import Path
import pickle
import sys
import tempfile
import types
import unittest

try:
    import gymnasium as gym
    import numpy as np
    import torch
    import stable_baselines3 as sb3
except ImportError:
    gym = None

from mvgrid.novi_sad.playground.continuous_ppo import train_policy, evaluate_policy


if gym is not None:
    class TinyEnv(gym.Env):
        def __init__(self, factory):
            self.observation_space = gym.spaces.Box(-10, 10, (3,), dtype=np.float32)
            self.action_space = gym.spaces.Box(-1, 1, (1,), dtype=np.float32)
            self.index = 0
            self.x = 0.0
            self.episode_metrics = {}

        def reset(self, *, seed=None, options=None):
            super().reset(seed=seed)
            self.index, self.x = 0, float(self.np_random.uniform(-1, 1))
            return self._obs(), {}

        def _obs(self):
            return np.array([self.x, self.index / 7, 1.0], dtype=np.float32)

        def step(self, action):
            self.x += float(action[0]) * .1 + float(self.np_random.normal(0, .01))
            self.index += 1
            self.episode_metrics = {'x': self.x, 'steps': self.index}
            return self._obs(), -self.x ** 2, self.index == 7, False, {'episode_metrics': dict(self.episode_metrics)}

        def get_state(self):
            return copy.deepcopy((self.index, self.x, self.np_random.bit_generator.state, self.episode_metrics))

        def set_state(self, state):
            self.index, self.x, rng, self.episode_metrics = copy.deepcopy(state)
            self.np_random.bit_generator.state = rng


@unittest.skipIf(gym is None, 'Optional continuous PPO dependencies are not installed')
class ContinuousPPOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.module = types.ModuleType('mvgrid.novi_sad.playground.continuous_env')
        self.module.ContinuousEVEnv = TinyEnv
        self.previous = sys.modules.get(self.module.__name__)
        sys.modules[self.module.__name__] = self.module

    def tearDown(self):
        if self.previous is None:
            sys.modules.pop(self.module.__name__, None)
        else:
            sys.modules[self.module.__name__] = self.previous
        self.tmp.cleanup()

    def train(self, name, steps, **kwargs):
        return train_policy(None, self.root / name, steps, seed=13, rollout_steps=8,
                            batch_size=8, n_epochs=2, binding={'network': 'frozen-a'}, **kwargs)

    def test_normalized_reward_resume_preserves_policy_and_return_statistics(self):
        options = dict(normalize_reward=True, initial_log_std=-1.)
        full = self.train('normalized-full', 32, **options)
        part = self.train('normalized-part', 16, **options)
        resumed = self.train('normalized-resume', 32, resume_from=part['checkpoint'], **options)
        self.assertEqual(full['episodes'], resumed['episodes'])
        models = [sb3.PPO.load(Path(r['checkpoint'])/'model.zip', device='cpu') for r in (full,resumed)]
        for key,value in models[0].policy.state_dict().items():
            self.assertTrue(torch.equal(value,models[1].policy.state_dict()[key]), key)
        self.assertLess(models[0].policy.log_std.exp().mean().item(), .5)
        normalizers = []
        for result in (full,resumed):
            with (Path(result['checkpoint'])/'normalization.pkl').open('rb') as stream:
                normalizers.append(pickle.load(stream))
        self.assertTrue(all(v.norm_reward for v in normalizers))
        np.testing.assert_array_equal(normalizers[0].ret_rms.mean,normalizers[1].ret_rms.mean)
        np.testing.assert_array_equal(normalizers[0].ret_rms.var,normalizers[1].ret_rms.var)
        with self.assertRaisesRegex(ValueError, 'configuration'):
            self.train('incompatible-normalization',32,resume_from=part['checkpoint'],initial_log_std=-1.)

    def test_exact_resume_matches_uninterrupted_actor_critic_optimizer_and_environment(self):
        for n_envs in (1, 2):
            with self.subTest(n_envs=n_envs):
                full = self.train(f'full{n_envs}', 32, n_envs=n_envs)
                part = self.train(f'part{n_envs}', 16, n_envs=n_envs)
                resumed = self.train(f'resume{n_envs}', 32, n_envs=n_envs, resume_from=part['checkpoint'])
                self.assertEqual(full['episodes'], resumed['episodes'])
                self.assertEqual(full['timesteps'], resumed['timesteps'])
                a, b = [sb3.PPO.load(Path(x['checkpoint']) / 'model.zip', device='cpu') for x in (full, resumed)]
                for key, value in a.policy.state_dict().items():
                    self.assertTrue(torch.equal(value, b.policy.state_dict()[key]), key)
                for key, state in a.policy.optimizer.state_dict()['state'].items():
                    for field, value in state.items():
                        self.assertTrue(torch.equal(value, b.policy.optimizer.state_dict()['state'][key][field]), field)
                with (Path(full['checkpoint']) / 'state.pkl').open('rb') as stream:
                    astate = pickle.load(stream)
                with (Path(resumed['checkpoint']) / 'state.pkl').open('rb') as stream:
                    bstate = pickle.load(stream)
                self.assertEqual(astate['environments'], bstate['environments'])
                np.testing.assert_array_equal(astate['last_obs'], bstate['last_obs'])
                moments = []
                for result in (full, resumed):
                    with (Path(result['checkpoint']) / 'normalization.pkl').open('rb') as stream:
                        moments.append(pickle.load(stream).obs_rms)
                np.testing.assert_array_equal(moments[0].mean, moments[1].mean)
                np.testing.assert_array_equal(moments[0].var, moments[1].var)
                self.assertEqual(moments[0].count, moments[1].count)

    def test_binding_and_hash_rejection(self):
        result = self.train('model', 8)
        with self.assertRaisesRegex(ValueError, 'binding'):
            evaluate_policy(result['checkpoint'], None, [1], binding={'network': 'different'})
        folder = Path(result['checkpoint'])
        with (folder / 'model.zip').open('ab') as stream:
            stream.write(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.train('resume', 16, resume_from=folder)

    def test_cancel_at_update_boundary_and_deterministic_evaluation(self):
        seen = []
        result = self.train('cancel', 32, cancellation=lambda: bool(seen), progress=seen.append)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(result['timesteps'], 8)
        self.assertEqual(result['completed_updates'], 1)
        binding = {'network': 'frozen-a'}
        a = evaluate_policy(result['checkpoint'], None, [40, 41], binding=binding)
        b = evaluate_policy(result['checkpoint'], None, [40, 41], binding=binding)
        self.assertEqual(a, b)
        self.assertEqual(a['completed_episodes'], 2)

    def test_deadline_before_training_does_not_claim_checkpoint(self):
        result = self.train('expired', 8, deadline=0)
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(result['timesteps'], 0)
        self.assertIsNone(result['checkpoint'])

    def test_partial_rollout_discarded_and_latest_pointer_resumes(self):
        calls = [0]
        def cancel():
            calls[0] += 1
            return calls[0] >= 13
        interrupted = self.train('partial', 32, cancellation=cancel)
        self.assertEqual(interrupted['status'], 'cancelled')
        self.assertEqual(interrupted['timesteps'], 8)
        self.assertEqual(interrupted['completed_updates'], 1)
        self.assertGreater(interrupted['partial_timesteps'], 0)
        self.assertLess(interrupted['partial_timesteps'], 8)
        resumed = self.train('resumed-pointer', 16, resume_from=self.root / 'partial')
        full = self.train('full-pointer', 16)
        self.assertEqual(resumed['episodes'], full['episodes'])
        a, b = [sb3.PPO.load(Path(x['checkpoint']) / 'model.zip', device='cpu') for x in (full, resumed)]
        for key, value in a.policy.state_dict().items():
            self.assertTrue(torch.equal(value, b.policy.state_dict()[key]), key)

    def test_environment_interrupt_during_reset_returns_no_fake_update(self):
        class Stop(InterruptedError):
            stop_reason = 'budget_exhausted'
        class InterruptedEnv(TinyEnv):
            def configure_stop(self, deadline, cancellation):
                self.configured = True
            def reset(self, **kwargs):
                if self.configured:
                    raise Stop()
                return super().reset(**kwargs)
        self.module.ContinuousEVEnv = InterruptedEnv
        result = self.train('reset-interrupted', 8)
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(result['timesteps'], 0)
        self.assertEqual(result['completed_updates'], 0)
        self.assertIsNone(result['checkpoint'])


if __name__ == '__main__':
    unittest.main()
