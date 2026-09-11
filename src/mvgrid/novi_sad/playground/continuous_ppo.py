"""CPU PPO with reproducible update-boundary checkpoints (trusted local files only)."""
from __future__ import annotations

import hashlib
import copy
import json
from pathlib import Path
import pickle
import random
import time


def _dependencies():
    try:
        import numpy as np
        import torch
        import stable_baselines3 as sb3
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    except ImportError as exc:
        raise RuntimeError("Continuous PPO requires gymnasium, torch and stable-baselines3. Install the project's RL dependencies.") from exc
    return np, torch, sb3, DummyVecEnv, VecNormalize


def _stop(deadline, cancellation):
    if cancellation is not None and (cancellation() if callable(cancellation) else cancellation.is_set()):
        return 'cancelled'
    if deadline is not None and time.monotonic() >= deadline:
        return 'budget_exhausted'
    return None


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_checkpoint(path):
    path = Path(path)
    pointer = path / 'latest.json' if path.is_dir() and not (path / 'manifest.json').exists() else path
    if pointer.is_file() and pointer.name == 'latest.json':
        return Path(json.loads(pointer.read_text(encoding='utf-8'))['checkpoint'])
    return path


def collect_llf_demonstrations(factory, folder, binding, episode_count, deadline=None, cancellation=None):
    """Cache training-only executed LLF labels; never query validation/test cases."""
    np, _, _, _, _ = _dependencies()
    from .continuous_env import ContinuousEVEnv, ContinuousStop
    from .strategies import create_controller
    if getattr(factory, 'split', None) != 'train':
        raise ValueError('LLF demonstrations require the training split.')
    folder = Path(folder)
    data_path, meta_path = folder/'llf-demonstrations.npz', folder/'llf-demonstrations.json'
    identity = dict(binding=binding, episodes=episode_count, seed_start=50000)
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta['identity'] != identity or _digest(data_path) != meta['sha256']:
            raise ValueError('LLF demonstration binding/integrity mismatch.')
        return data_path
    observations, labels, masks, evidence = [], [], [], []
    env = ContinuousEVEnv(copy.deepcopy(factory))
    env.configure_stop(deadline, cancellation)
    try:
        for i in range(episode_count):
            obs, _ = env.reset(seed=50000+i)
            controller = create_controller('least_laxity_first', env.sim.case.get('strategy_options'))
            while not env._done:
                reason = _stop(deadline, cancellation)
                if reason:
                    raise ContinuousStop(reason)
                result, label, mask = env.teacher_step(controller)
                observations.append(obs.copy()); labels.append(label); masks.append(mask)
                obs = result[0]
            evidence.append(dict(metadata=env.episode_metadata, metrics=env.episode_metrics,
                safety_intervals=sum(bool(x.get('safety_iterations')) for x in env.sim.intervals)))
    finally:
        env.close()
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(data_path, observations=np.asarray(observations), actions=np.asarray(labels), masks=np.asarray(masks))
    meta_path.write_text(json.dumps(dict(identity=identity, sha256=_digest(data_path),
        evidence=evidence, teacher='least_laxity_first with existing AC protection',
        limitation='Executed cohort powers aggregated to nodes; PPO uses earliest-departure allocation.'), indent=2), encoding='utf-8')
    return data_path


def initialize_from_demonstrations(model, vec, data_path, epochs, deadline=None, cancellation=None):
    """Fit actor means on active-node labels; keep PPO optimizer state fresh."""
    np, torch, _, _, _ = _dependencies()
    from .continuous_env import ContinuousStop
    with np.load(data_path, allow_pickle=False) as data:
        obs, actions, masks = (data[k].copy() for k in ('observations', 'actions', 'masks'))
    if not np.isfinite(obs).all() or not np.isfinite(actions).all() or not masks.any():
        raise ValueError('Invalid or empty active-node demonstration data.')
    vec.obs_rms.update(obs)
    x = torch.as_tensor(vec.normalize_obs(obs), dtype=torch.float32)
    y = torch.as_tensor(actions, dtype=torch.float32)
    mask = torch.as_tensor(masks, dtype=torch.float32)
    optimizer = torch.optim.Adam(model.policy.parameters(), lr=1e-3)
    def loss(indices):
        mean = model.policy.get_distribution(x[indices]).distribution.mean
        return (((mean-y[indices])**2)*mask[indices]).sum()/mask[indices].sum().clamp(min=1.)
    with torch.no_grad():
        before = float(loss(slice(None)))
    for _ in range(epochs):
        for ids in torch.randperm(len(x)).split(256):
            reason = _stop(deadline, cancellation)
            if reason:
                raise ContinuousStop(reason)
            optimizer.zero_grad(); objective = loss(ids); objective.backward()
            torch.nn.utils.clip_grad_norm_(model.policy.parameters(), 1.)
            optimizer.step()
    with torch.no_grad():
        after = float(loss(slice(None)))
    return dict(active_node_mse_before=before, active_node_mse_after=after,
                transitions=len(x), epochs=epochs, dataset_sha256=_digest(Path(data_path)))


def _manifest(path, binding):
    path = _resolve_checkpoint(path)
    data = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if data.get('format') != 1 or data.get('binding') != binding:
        raise ValueError('Checkpoint binding or format is incompatible with this request.')
    for name in ('model.zip', 'normalization.pkl', 'state.pkl'):
        if _digest(path / name) != data['sha256'].get(name):
            raise ValueError(f'Checkpoint integrity check failed: {name}')
    return data


def _checkpoint(model, vec, output_dir, binding, config, updates, episodes, np, torch, sb3):
    folder = Path(output_dir) / f'update-{updates:06d}'
    folder.mkdir(parents=True, exist_ok=False)
    model.save(folder / 'model.zip')
    vec.save(folder / 'normalization.pkl')
    dummy = vec.venv
    state = {
        'python_rng': random.getstate(), 'numpy_rng': np.random.get_state(),
        'torch_rng': torch.get_rng_state(),
        'environments': dummy.env_method('get_state'),
        'dummy': {k: getattr(dummy, k) for k in ('buf_obs', 'buf_dones', 'buf_rews', 'buf_infos', 'reset_infos', '_seeds', '_options')},
        'returns': vec.returns, 'last_obs': model._last_obs,
        'last_original_obs': model._last_original_obs,
        'last_episode_starts': model._last_episode_starts,
        'episodes': episodes,
    }
    with (folder / 'state.pkl').open('wb') as stream:
        pickle.dump(state, stream, protocol=pickle.HIGHEST_PROTOCOL)
    manifest = {'format': 1, 'binding': binding, 'config': config, 'updates': updates,
                'timesteps': model.num_timesteps, 'episodes': len(episodes),
                'versions': {'sb3': sb3.__version__, 'torch': torch.__version__, 'numpy': np.__version__},
                'sha256': {name: _digest(folder / name) for name in ('model.zip', 'normalization.pkl', 'state.pkl')}}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding='utf-8')
    pointer = Path(output_dir) / '.latest.tmp'
    pointer.write_text(json.dumps({'checkpoint': str(folder.resolve())}), encoding='utf-8')
    pointer.replace(Path(output_dir) / 'latest.json')
    return str(folder.resolve())


def train_policy(episode_factory, output_dir, total_timesteps, learning_rate=3e-4,
                 seed=0, n_envs=1, resume_from=None, deadline=None,
                 cancellation=None, progress=None, binding=None,
                 rollout_steps=1024, batch_size=128, n_epochs=5,
                 target_kl=.02, entropy_coef=0., vf_coef=.5, max_grad_norm=.5,
                 normalize_reward=False, initial_log_std=0.,
                 llf_warmstart_episodes=0, llf_warmstart_epochs=30):
    """Train to a cumulative timestep target; checkpoint only complete updates.

    Deadline is an absolute monotonic time. Resume files must be trusted local
    artifacts: SHA256 detects corruption, not malicious pickle replacement.
    """
    np, torch, sb3, DummyVecEnv, VecNormalize = _dependencies()
    from .continuous_env import ContinuousEVEnv
    if n_envs not in (1, 2) or total_timesteps < 1 or rollout_steps < 2 or batch_size < 2 or n_epochs < 1:
        raise ValueError('Use one or two environments and positive training sizes (rollout/batch >= 2).')
    if rollout_steps % n_envs or rollout_steps // n_envs < 2 or rollout_steps % batch_size:
        raise ValueError('Total rollout_steps must divide evenly over environments and batch_size; each environment needs >= 2 steps.')
    if not np.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError('learning_rate must be finite and positive.')
    if not isinstance(normalize_reward, bool) or not np.isfinite(initial_log_std) or not -5 <= initial_log_std <= 1:
        raise ValueError('Use a boolean normalize_reward and finite initial_log_std in [-5, 1].')
    if not isinstance(llf_warmstart_episodes, int) or not 0 <= llf_warmstart_episodes <= 256 or not isinstance(llf_warmstart_epochs, int) or not 1 <= llf_warmstart_epochs <= 500:
        raise ValueError('Invalid LLF warm-start sizes.')
    grid_penalty_normalization = getattr(episode_factory,'grid_penalty_normalization','none')
    if grid_penalty_normalization not in ('none','episode_horizon'):
        raise ValueError('Unsupported grid penalty normalization.')
    torch.set_num_threads(1)
    config = dict(learning_rate=learning_rate, seed=seed, n_envs=n_envs,
                  rollout_steps=rollout_steps, batch_size=batch_size, n_epochs=n_epochs,
                  target_kl=target_kl, entropy_coef=entropy_coef, vf_coef=vf_coef, max_grad_norm=max_grad_norm,
                  normalize_reward=normalize_reward, initial_log_std=initial_log_std,
                  grid_penalty_normalization=grid_penalty_normalization,
                  llf_warmstart_episodes=llf_warmstart_episodes, llf_warmstart_epochs=llf_warmstart_epochs)
    resume_from = _resolve_checkpoint(resume_from) if resume_from else None
    manifest = _manifest(resume_from, binding) if resume_from else None
    if manifest and {'normalize_reward':False, 'initial_log_std':0., 'llf_warmstart_episodes':0,
                     'llf_warmstart_epochs':30, 'grid_penalty_normalization':'none', **manifest['config']} != config:
        raise ValueError('Checkpoint training configuration is incompatible.')
    versions = {'sb3': sb3.__version__, 'torch': torch.__version__, 'numpy': np.__version__}
    if manifest and manifest['versions'] != versions:
        raise ValueError('Checkpoint dependency versions differ; exact resume is not supported.')
    # Pure seed factories may be shared; stateful callable objects get isolated copies.
    factories = [copy.deepcopy(episode_factory) for _ in range(n_envs)]
    dummy = DummyVecEnv([lambda factory=factory: ContinuousEVEnv(factory) for factory in factories])
    episodes, updates, checkpoint = [], 0, None
    partial_timesteps = 0
    initialization_timing = dict(collection_seconds=0., fitting_seconds=0.)
    vec = None
    try:
        if resume_from:
            folder = Path(resume_from)
            vec = VecNormalize.load(folder / 'normalization.pkl', dummy)
            model = sb3.PPO.load(folder / 'model.zip', env=vec, device='cpu', force_reset=False)
            with (folder / 'state.pkl').open('rb') as stream:
                state = pickle.load(stream)
            for index, env_state in enumerate(state['environments']):
                dummy.env_method('set_state', env_state, indices=index)
            for key, value in state['dummy'].items():
                setattr(dummy, key, value)
            vec.returns = state['returns']
            model._last_obs = state['last_obs']
            model._last_original_obs = state['last_original_obs']
            model._last_episode_starts = state['last_episode_starts']
            random.setstate(state['python_rng'])
            np.random.set_state(state['numpy_rng'])
            torch.set_rng_state(state['torch_rng'])
            episodes, updates, checkpoint = state['episodes'], manifest['updates'], str(folder.resolve())
        else:
            vec = VecNormalize(dummy, norm_obs=True, norm_reward=normalize_reward, gamma=.999)
            model = sb3.PPO('MlpPolicy', vec, learning_rate=learning_rate,
                            n_steps=rollout_steps // n_envs, batch_size=batch_size, n_epochs=n_epochs,
                            gamma=.999, gae_lambda=.95, clip_range=.2, seed=seed,
                            target_kl=target_kl, ent_coef=entropy_coef, vf_coef=vf_coef, max_grad_norm=max_grad_norm,
                            device='cpu', policy_kwargs={'activation_fn': torch.nn.Tanh, 'log_std_init':initial_log_std,
                            'net_arch': {'pi': [128, 128], 'vf': [128, 128]}}, verbose=0)
            if llf_warmstart_episodes:
                initialization_phase = 'collection_seconds'
                initialization_started = time.perf_counter()
                try:
                    reason = _stop(deadline, cancellation)
                    if reason:
                        from .continuous_env import ContinuousStop
                        raise ContinuousStop(reason)
                    data_path = collect_llf_demonstrations(episode_factory, Path(output_dir).parent,
                        binding, llf_warmstart_episodes, deadline, cancellation)
                    initialization_timing[initialization_phase] = time.perf_counter()-initialization_started
                    initialization_phase = 'fitting_seconds'
                    initialization_started = time.perf_counter()
                    initialization = initialize_from_demonstrations(model, vec, data_path,
                        llf_warmstart_epochs, deadline, cancellation)
                    initialization_timing[initialization_phase] = time.perf_counter()-initialization_started
                except Exception as exc:
                    reason = getattr(exc, 'stop_reason', None)
                    if reason not in ('cancelled', 'budget_exhausted'):
                        raise
                    initialization_timing[initialization_phase] = time.perf_counter()-initialization_started
                    return dict(status=reason, completed_updates=0, timesteps=0, partial_timesteps=0,
                                episodes=[], checkpoint=None, initialization_timing=initialization_timing)
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                (Path(output_dir)/'initialization.json').write_text(json.dumps({**initialization, 'timing':initialization_timing}, indent=2))
        for env in dummy.envs:
            if hasattr(env.unwrapped, 'configure_stop'):
                env.unwrapped.configure_stop(deadline, cancellation)
        stop_reason = None
        def collect(locals_, globals_):
            nonlocal stop_reason
            stop_reason = _stop(deadline, cancellation)
            if stop_reason:
                return False
            for done, info in zip(locals_['dones'], locals_['infos']):
                if done and 'episode_metrics' in info:
                    episodes.append(info['episode_metrics'])
            return True
        status = 'completed'
        committed_timesteps = model.num_timesteps
        while model.num_timesteps < total_timesteps:
            status = _stop(deadline, cancellation) or 'completed'
            if status != 'completed':
                break
            episode_count = len(episodes)
            try:
                model.learn(total_timesteps=rollout_steps, reset_num_timesteps=False, callback=collect)
            except Exception as exc:
                stop_reason = getattr(exc, 'stop_reason', None)
                if stop_reason not in ('cancelled', 'budget_exhausted'):
                    raise
            if stop_reason:
                status = stop_reason
                partial_timesteps = model.num_timesteps - committed_timesteps
                del episodes[episode_count:]
                break
            updates += 1
            committed_timesteps = model.num_timesteps
            checkpoint = _checkpoint(model, vec, output_dir, binding, config, updates, episodes, np, torch, sb3)
            if progress:
                progress({'completed_updates': updates, 'timesteps': model.num_timesteps,
                          'episodes': len(episodes), 'checkpoint': checkpoint})
        return {'status': status, 'completed_updates': updates, 'timesteps': committed_timesteps,
                'partial_timesteps': partial_timesteps, 'episodes': episodes, 'checkpoint': checkpoint,
                'initialization_timing': initialization_timing}
    finally:
        (vec if vec is not None else dummy).close()


def evaluate_policy(model_path, episode_factory, seeds, deadline=None, cancellation=None, binding=None):
    """Deterministic held-out evaluation with frozen training observation moments."""
    np, torch, sb3, DummyVecEnv, VecNormalize = _dependencies()
    from .continuous_env import ContinuousEVEnv
    model_path = _resolve_checkpoint(model_path)
    manifest = _manifest(model_path, binding)
    if manifest['config'].get('grid_penalty_normalization','none') != getattr(episode_factory,'grid_penalty_normalization','none'):
        raise ValueError('Evaluation reward configuration differs from the checkpoint.')
    dummy = DummyVecEnv([lambda: ContinuousEVEnv(episode_factory)])
    if hasattr(dummy.envs[0].unwrapped, 'configure_stop'):
        dummy.envs[0].unwrapped.configure_stop(deadline, cancellation)
    vec = VecNormalize.load(Path(model_path) / 'normalization.pkl', dummy)
    vec.training, vec.norm_reward = False, False
    model = sb3.PPO.load(Path(model_path) / 'model.zip', env=vec, device='cpu')
    results, status = [], 'completed'
    try:
        for seed in seeds:
            status = _stop(deadline, cancellation) or 'completed'
            if status != 'completed':
                break
            vec.seed(int(seed))
            obs, done, reward_sum, steps = vec.reset(), False, 0.0, 0
            reset_info = copy.deepcopy(dummy.reset_infos[0])
            while not done:
                status = _stop(deadline, cancellation) or 'completed'
                if status != 'completed':
                    break
                action, _ = model.predict(obs, deterministic=True)
                obs, rewards, dones, infos = vec.step(action)
                reward_sum += float(rewards[0])
                steps += 1
                done = bool(dones[0])
            if status != 'completed':
                break
            results.append({'seed': int(seed), 'reward': reward_sum, 'steps': steps,
                            'episode_metadata': reset_info.get('metadata', {}),
                            'metrics': infos[0].get('episode_metrics', {})})
    except Exception as exc:
        status = getattr(exc, 'stop_reason', None)
        if status not in ('cancelled', 'budget_exhausted'):
            raise
    finally:
        vec.close()
    return {'status': status, 'episodes': results, 'completed_episodes': len(results),
            'checkpoint': str(Path(model_path).resolve())}
