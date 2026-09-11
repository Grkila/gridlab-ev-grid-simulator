"""Frozen, budgeted node-PPO campaigns, independent of historical binary policies."""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

import numpy as np
from pydantic import Field, model_validator
from mvgrid.paths import REPOSITORY_ROOT
from .schema import StrictModel
from .service import Service, digest, read_json, write_json

ACTIVE = ('queued', 'starting', 'running')
MODEL_FILES = ('benchmark.py', 'simulation.py', 'demand.py', 'charging_profiles.py', 'network.py', 'node_aggregation.py',
               'loss_accounting.py', 'operating_scenario.py', 'capacity_layers.py',
               'districts.py', 'strategies.py', 'smoothed_llf.py', 'valley_odc.py', 'feeder_equivalent.py', 'capacity_alignment.py', 'schema.py')
FAMILIES = {'city_max': 'normal', 'city_worst_max': 'worst',
            'district_max': 'district', 'district_worst_max': 'district_worst'}
BASELINES = ('capacity_aware', 'least_laxity_first', 'valley_filling', 'all_demand',
             'fixed_delay', 'randomized_delay', 'voltage_responsive')


class CampaignConfig(StrictModel):
    algorithm: Literal['node_ppo'] = 'node_ppo'
    anchor_strategy: Literal['capacity_aware'] = 'capacity_aware'
    objective: Literal['outperform_baselines'] = 'outperform_baselines'
    target_fleet: int | None = Field(default=None, ge=1, le=1000000)
    budget_hours: float = Field(default=10, ge=1, le=12, allow_inf_nan=False)
    learning_rates: list[float] = Field(default_factory=lambda: [1e-4, 3e-4, 1e-3], min_length=1, max_length=3)
    training_timesteps: int | None = Field(default=None, ge=8192, le=1000000)
    llf_warmstart_episodes: int = Field(default=0, ge=0, le=256)
    llf_warmstart_epochs: int = Field(default=30, ge=1, le=500)
    grid_penalty_normalization: Literal['none','episode_horizon'] = 'none'
    normalize_reward: bool = False
    initial_log_std: float = Field(default=0., ge=-5, le=1, allow_inf_nan=False)
    initialization_seeds: list[int] = Field(default_factory=lambda: [7101, 7102, 7103], min_length=3, max_length=3)
    training_seed_base: int = Field(default=100000, ge=0, le=2**31)
    validation_seed_base: int = Field(default=200000, ge=0, le=2**31)
    test_seed_base: int = Field(default=300000, ge=0, le=2**31)
    pilot_seconds: float = Field(default=3600, ge=10, le=3600, allow_inf_nan=False)
    queue_timeout_seconds: float = Field(default=43200, ge=1, le=86400, allow_inf_nan=False)

    @model_validator(mode='after')
    def valid(self):
        if any(not math.isfinite(x) or not 0 < x <= .1 for x in self.learning_rates):
            raise ValueError('Learning rates must be finite and in (0, .1].')
        if len(set(self.learning_rates)) != len(self.learning_rates) or len(set(self.initialization_seeds)) != 3:
            raise ValueError('Use distinct learning rates and three distinct initialization seeds.')
        if any(not 0 <= x < 2**31 for x in self.initialization_seeds):
            raise ValueError('Initialization seeds must be nonnegative 31-bit integers.')
        starts = sorted([self.training_seed_base, self.validation_seed_base, self.test_seed_base])
        if any(b-a < 100000 for a,b in zip(starts, starts[1:])):
            raise ValueError('Training, validation and final-test seed ranges must be disjoint (100000 each).')
        if any(s <= 41001 < s+100000 for s in starts):
            raise ValueError('Reserved benchmark seed 41001 cannot belong to a campaign split.')
        return self


def runtime_binding():
    folder = Path(__file__).parent
    names = (*MODEL_FILES, 'continuous_env.py', 'continuous_ppo.py', 'continuous_campaign.py')
    from .continuous_env import ENV_VERSION, NODE_FEATURES, GLOBAL_FEATURES, REWARD_FORMULA
    return {'environment_version':ENV_VERSION, 'node_features':list(NODE_FEATURES),
            'global_features':list(GLOBAL_FEATURES), 'reward_formula':REWARD_FORMULA, 'source': {n: hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in names},
            'dependencies': {n: importlib.metadata.version(n) for n in
                             ('numpy', 'pandas', 'scipy', 'pandapower', 'torch', 'gymnasium', 'stable-baselines3')}}


def anchors_from_results(rows):
    anchors = {}
    for row in rows:
        family = FAMILIES.get(row.get('test_id'))
        if (not family or row.get('status') != 'bounded' or not row.get('fleet_size')
                or row.get('baseline', {}).get('status') != 'passed'):
            continue
        if row['strategy'] == 'mpc':
            continue
        previous = anchors.get(family, {})
        if row['fleet_size'] > previous.get('fleet_size', 0):
            anchors[family] = {'fleet_size': row['fleet_size'], 'strategy': row['strategy'],
                               'test_id': row['test_id'], 'next_failed_fleet': row.get('next_failed_fleet'),
                               'evidence': next(a for a in row['attempts'] if a['fleet_size'] == row['fleet_size'] and a['status'] == 'passed')}
    if 'normal' not in anchors:
        raise ValueError('A complete bounded normal-city row with a passing zero-EV baseline is required.')
    return anchors


class FrozenEpisodeFactory:
    """Pick immutable episode inputs; a seed changes vehicles, never the horizon."""
    def __init__(self, folder, split='train', fixed_case=None):
        self.folder = Path(folder)
        self.request = read_json(self.folder/'request.json')
        self.fixture = read_json(self.folder/'fixtures.json')
        self.node_ids = sorted(b['id'] for b in self.fixture['blocks'])
        self.split = split
        self.grid_penalty_normalization = self.request['config'].get('grid_penalty_normalization','none')
        self.fixed_case = fixed_case
        expected = self.request['fixture_hash']
        if digest(self.fixture) != expected:
            raise ValueError('Frozen episode fixtures changed.')
        if hashlib.sha256((self.folder/'network.json').read_bytes()).hexdigest() != self.request['network_hash']:
            raise ValueError('Frozen episode network changed.')

    def __call__(self, seed):
        from .benchmark import session_pool
        from .demand import allocate_block_demand
        seed = int(seed)
        base = 0 if self.split == 'benchmark' else self.request['config'][{'train':'training_seed_base', 'validation':'validation_seed_base', 'test':'test_seed_base'}[self.split]]
        day_seed = seed if self.split == 'benchmark' else base + seed % 100000
        rng = np.random.default_rng(day_seed)
        families = list(self.request['anchors'])
        if self.fixed_case is None:
            family = families[int(rng.integers(len(families)))]
            band = int(rng.choice(3, p=[.25, .5, .25]))
            fraction = float(rng.choice(((.25, .5), (.8, .95), (1., 1.05))[band]))
            count = max(1, int(round(self.request['anchors'][family]['fleet_size']*fraction)))
            if band == 2:
                strongest = self.request.get('comparison_anchors',{}).get(family,self.request['anchors'][family])['fleet_size']
                count = max(count,round(strongest*fraction))
                if family == 'normal' and self.request['config'].get('target_fleet'):
                    count = max(count,round(self.request['config']['target_fleet']*fraction))
        else:
            family, count = self.fixed_case
        profile_name = 'worst' if family == 'district_worst' else 'normal' if family in ('district','synchronized') else family
        profile = copy.deepcopy(self.fixture['demand'][profile_name])
        district = self.fixture['config']['district'] if family.startswith('district') else None
        sessions = session_pool(self.fixture['blocks'], day_seed, count, district, family == 'synchronized',
                                self.fixture['config'].get('charging_profile', 'home_only'))
        horizon = self.request['horizon_steps']
        if len(profile) != horizon or any(s['departure_step'] > horizon for s in sessions):
            raise ValueError('Episode cannot change the frozen completion horizon.')
        case = dict(strategy='immediate', fixed_start_hour=23, seed=day_seed, aggregate_ev_nodes=True,
                    stop_on_violation=False, limits=self.fixture['limits'],
                    demand_measurement='supply_including_losses',
                    network_path=str(self.folder/'network.json'), blocks=self.fixture['blocks'],
                    resolved_districts=self.fixture['districts'], network_capacity=self.fixture['network_capacity'],
                    strategy_options=self.request.get('benchmark_strategy_options',{}),
                    block_demand_kw=allocate_block_demand(profile, self.fixture['blocks'], {}))
        return dict(case=case, demand_kw=profile, sessions=sessions,
                    reward_config={'grid_penalty_normalization':self.grid_penalty_normalization},
                    metadata=dict(seed=day_seed, split=self.split, family=family, fleet_size=count,
                                  demand_hash=digest(profile), replay_hash=digest(sessions), horizon_steps=horizon))


class ContinuousCampaignService:
    def __init__(self, root=None):
        self.service = Service(root)
        self.root = self.service.root

    def folder(self, campaign_id):
        import re
        if not re.fullmatch(r'ppo-[a-f0-9]{20}', campaign_id):
            raise ValueError('Use a returned PPO campaign ID.')
        return self.service._path('continuous-rl', campaign_id)

    def catalog(self):
        return dict(algorithm='node_ppo', defaults=CampaignConfig().model_dump(),
                    action_space='continuous node kW with earliest-departure allocation',
                    campaigns=[self.get(p.parent.name) for p in sorted((self.root/'continuous-rl').glob('*/state.json'))],
                    legacy_note='Binary REINFORCE models cannot be loaded as continuous node policies.')

    def get(self, campaign_id):
        folder = self.folder(campaign_id)
        state = read_json(folder/'state.json')
        if state['status'] in ACTIVE and state.get('pid'):
            import psutil
            if not psutil.pid_exists(state['pid']):
                if state['status'] == 'running' and state.get('last_active_wall_time'):
                    state['elapsed_seconds'] = state.get('elapsed_seconds',0)+max(0,time.time()-state['last_active_wall_time'])
                state = {**state, 'status':'interrupted', 'error':'Campaign worker exited; inspect checkpoints before resuming.'}
        return state

    def results(self, campaign_id):
        folder = self.folder(campaign_id)
        return dict(campaign=self.get(campaign_id), request=read_json(folder/'request.json'),
                    report=read_json(folder/'report.json') if (folder/'report.json').exists() else None)

    def create(self, benchmark_job_id, config=None):
        from .benchmark import BenchmarkService
        cfg = CampaignConfig.model_validate(config or {}).model_dump()
        benchmark = BenchmarkService(self.root)
        result = benchmark.results(benchmark_job_id)
        fixture = benchmark.get_suite(result['request']['suite_id'])
        if not fixture['config'].get('aggregate_ev_nodes') or fixture['config'].get('operating_mode') != 'regulated':
            raise ValueError('Use a regulated, node-aggregated benchmark suite.')
        if fixture.get('demand_measurement') != 'supply_including_losses':
            raise ValueError('Continuous campaign requires the gross-supply measurement boundary.')
        for name in MODEL_FILES:
            expected = result['request']['fingerprint']['source_hashes'].get(name)
            actual = hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
            if expected != actual:
                raise ValueError(f'Benchmark model source differs: {name}. Replay anchor evidence on the current simulator.')
        for name in ('numpy','pandas','scipy','pandapower'):
            if result['request']['fingerprint']['dependencies'].get(name) != importlib.metadata.version(name):
                raise ValueError(f'Benchmark numerical dependency changed: {name}.')
        for seed in fixture['config']['seeds']:
            if any(cfg[k] <= seed < cfg[k]+100000 for k in ('training_seed_base','validation_seed_base','test_seed_base')):
                raise ValueError('Campaign seed ranges overlap frozen benchmark seeds.')
        anchors = anchors_from_results([r for r in result['rows'] if r['strategy'] == cfg['anchor_strategy']])
        horizons = {len(v) for v in fixture['demand'].values()}
        if len(horizons) != 1:
            raise ValueError('Freeze a common complete horizon before creating a campaign.')
        from .continuous_env import reward_formula
        horizon = next(iter(horizons))
        reward_configuration = dict(grid_penalty_normalization=cfg['grid_penalty_normalization'],
            grid_penalty_divisor=horizon if cfg['grid_penalty_normalization']=='episode_horizon' else 1,
            formula=reward_formula(cfg['grid_penalty_normalization']))
        comparison_anchors = anchors_from_results(result['rows'])
        binding = runtime_binding()
        network = benchmark.path('benchmark-suites', result['request']['suite_id'])/'network.json'
        # Vehicle pools are regenerated by the frozen seeded mechanism, not copied at every episode.
        frozen = {k:v for k,v in fixture.items() if k != 'pools'}
        request = dict(config=cfg, reward_configuration=reward_configuration, case_origin='llm', node_ids=sorted(b['id'] for b in fixture['blocks']), benchmark_job_id=benchmark_job_id, suite_id=result['request']['suite_id'],
                       benchmark_complete=result['complete'], anchors=anchors, comparison_anchors=comparison_anchors,
                       anchor_selection='Capacity-aware passing tested bounds provide deterministic curriculum scaling; timed optimizer competitors remain in held-out evaluation.', horizon_steps=horizons.pop(),
                       benchmark_strategy_options=result['request']['config']['strategy_options'],
                       fixture_hash=digest(frozen), network_hash=hashlib.sha256(network.read_bytes()).hexdigest(),
                       binding=binding, created_at=datetime.now(timezone.utc).isoformat())
        campaign_id = 'ppo-'+digest(request)[:20]
        folder = self.folder(campaign_id)
        folder.mkdir(parents=True, exist_ok=False)
        write_json(folder/'request.json', request)
        write_json(folder/'fixtures.json', frozen)
        write_json(folder/'benchmark-evidence.json', result)
        shutil.copyfile(network, folder/'network.json')
        state = dict(campaign_id=campaign_id, status='prepared', phase='prepared', pid=None,
                     created_at=request['created_at'], elapsed_seconds=0., scientific_verdict='not_evaluated')
        write_json(folder/'state.json', state)
        return state

    def start(self, campaign_id, resume=False):
        from filelock import FileLock
        folder = self.folder(campaign_id)
        with FileLock(str(folder/'launch.lock'), timeout=30):
            return self._start_locked(campaign_id, resume)

    def _start_locked(self, campaign_id, resume=False):
        folder = self.folder(campaign_id)
        state = self.get(campaign_id)
        if state['status'] in ACTIVE:
            return state
        if state['status'] == 'completed':
            raise ValueError('Completed campaigns are immutable; create a new campaign.')
        if state['status'] != 'prepared' and not resume:
            raise ValueError('Use explicit resume for an interrupted campaign.')
        request = read_json(folder/'request.json')
        if request['binding'] != runtime_binding():
            raise ValueError('Campaign source/dependencies changed; create a fresh campaign.')
        (folder/'cancel').unlink(missing_ok=True)
        state.update(status='queued', phase='waiting_for_worker', pid=None)
        write_json(folder/'state.json', state)
        try:
            with (folder/'worker.log').open('a', encoding='utf-8') as log:
                p = subprocess.Popen([sys.executable, '-m', __name__, str(self.root), campaign_id],
                    cwd=REPOSITORY_ROOT, env={**os.environ, 'PYTHONPATH':str(REPOSITORY_ROOT/'src')},
                    stdout=log, stderr=log, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception as exc:
            state.update(status='failed', phase='launch_failed', pid=None, error=str(exc))
            write_json(folder/'state.json', state)
            raise
        state['pid'] = p.pid
        write_json(folder/'state.json', state)
        return state

    def cancel(self, campaign_id):
        state = self.get(campaign_id)
        active = state['status'] in ACTIVE
        if active:
            (self.folder(campaign_id)/'cancel').touch()
        return dict(campaign_id=campaign_id, cancel_requested=active)


def _acquire_worker(service, campaign_id, check):
    lock = service.root/'worker.lock'
    while True:
        check()
        try:
            fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            with os.fdopen(fd, 'w') as f:
                f.write(campaign_id)
            return
        except FileExistsError:
            owner = lock.read_text().strip()
            if owner:
                try:
                    state = service.get(owner) if owner.startswith('ppo-') else service.service.get_run(owner)
                except FileNotFoundError:
                    state = {'status':'unknown'}
                if state['status'] not in (*ACTIVE, 'unknown'):
                    if lock.read_text().strip() == owner:
                        lock.unlink(missing_ok=True)
                    continue
            time.sleep(1)


def _score(rows):
    rows = [r.get('metrics',r) for r in rows]
    if not rows or any(not r.get('complete', False) for r in rows):
        return None
    return (sum(not r.get('passed', False) for r in rows),
            sum(r.get('unmet_energy_kwh', 0) for r in rows),
            sum(r.get('violation_intervals', r.get('violation_steps', 0)) for r in rows),
            sum(r.get('peak_demand_kw') if r.get('peak_demand_kw') is not None else math.inf for r in rows))


def _episode_identity(row):
    metadata = row.get('episode_metadata') or row.get('metrics',{}).get('episode_metadata') or row
    keys = ('family','fleet_size','seed','demand_hash','replay_hash')
    return tuple(metadata.get(k) for k in keys)


def _episode_valid(row):
    metrics = row.get('metrics',row)
    if metrics.get('numerical_invalid',False) or metrics.get('nonconverged_steps',0):
        return False
    if 'status' in row:
        return row['status'] in ('passed','failed') and row.get('complete',False)
    metrics = row.get('metrics',row)
    return metrics.get('complete',False) and not metrics.get('numerical_invalid',False)


def _episode_passed(row):
    return _episode_valid(row) and (row.get('status') == 'passed' if 'status' in row else row.get('metrics',row).get('passed',False))


def compare_validation(episodes, baselines):
    """Paired evidence only: unknowns, hash changes and missed service never win."""
    results = {}
    indexed = {_episode_identity(e):e for e in episodes}
    identities_valid = len(indexed) == len(episodes) and bool(episodes) and all(None not in key for key in indexed)
    for name, rows in baselines.items():
        reference = {_episode_identity(e):e for e in rows}
        valid = identities_valid and len(reference) == len(rows) and set(reference) == set(indexed) and all(_episode_valid(e) for e in [*episodes,*rows])
        wins = regressions = 0
        peaks = []
        relative_peaks = []
        if valid:
            for key, e in indexed.items():
                baseline=reference[key]
                passed, baseline_passed = _episode_passed(e),_episode_passed(baseline)
                wins += int(passed and not baseline_passed)
                regressions += int(baseline_passed and not passed)
                if passed and baseline_passed:
                    a,b=e.get('metrics',e),baseline.get('metrics',baseline)
                    requested=[a.get('requested_energy_kwh'),b.get('requested_energy_kwh')]
                    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<0 for v in requested):
                        valid=False
                        break
                    if not math.isclose(*requested,rel_tol=1e-10,abs_tol=1e-5):
                        valid=False
                        break
                    left,right=a.get('peak_demand_kw'),b.get('peak_demand_kw')
                    if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in (left,right)):
                        valid=False
                        break
                    peaks.append(left-right)
                    relative_peaks.append((left-right)/max(abs(right),1.))
        results[name] = dict(complete_valid=bool(valid), feasibility_wins=wins if valid else None,
                             feasibility_regressions=regressions if valid else None,
                             feasible_peak_deltas_kw=peaks if valid else [],
                             feasible_peak_relative_deltas=relative_peaks if valid else [],
                             paired_cases=len(indexed) if valid else 0)
    return results


def validation_baselines(folder,request,cases,report,deadline,check,save):
    from .simulation import simulate_case
    from .benchmark import trial_summary
    recorded=report.setdefault('validation_baselines',{})
    for strategy in BASELINES:
        if len(recorded.get(strategy,[])) == len(cases)*2:
            continue
        trials=[]
        for family,count in cases:
            factory=FrozenEpisodeFactory(folder,'validation',(family,count))
            for seed in (0,1):
                def progress(_=None):
                    check()
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Matched validation baseline budget exhausted.')
                progress()
                episode=factory(seed)
                outcome=trial_summary(simulate_case({**episode['case'],'strategy':'immediate' if strategy=='all_demand' else strategy},episode['demand_kw'],episode['sessions'],progress))
                trials.append({**episode['metadata'],**outcome})
        recorded[strategy]=trials
        save()
    return recorded


def run_campaign(root, campaign_id):
    """One serial campaign, queued behind existing work; all budgets include resets."""
    from .continuous_ppo import train_policy, evaluate_policy
    service = ContinuousCampaignService(root)
    folder = service.folder(campaign_id)
    state = read_json(folder/'state.json')
    for _ in range(100):
        if state.get('pid'):
            break
        time.sleep(.05)
        state = read_json(folder/'state.json')
    request = read_json(folder/'request.json')
    cfg = request['config']
    report = read_json(folder/'report.json') if (folder/'report.json').exists() else {'trials':[], 'evaluation':[], 'preflight':[]}
    started = None
    previous_elapsed = float(state.get('elapsed_seconds', 0))
    queued_at = time.monotonic()
    acquired = False

    def save():
        if started is not None:
            state['elapsed_seconds'] = previous_elapsed+time.monotonic()-started
            state['last_active_wall_time'] = time.time()
        write_json(folder/'state.json', state)
        write_json(folder/'report.json', report)

    def check():
        if (folder/'cancel').exists():
            raise InterruptedError('Campaign cancelled; completed checkpoints retained.')
        if started is None:
            if time.monotonic()-queued_at > cfg['queue_timeout_seconds']:
                raise TimeoutError('Queue wait budget exhausted; no training claimed.')
        elif previous_elapsed+time.monotonic()-started >= min(cfg['budget_hours'],12)*3600:
            raise TimeoutError('Campaign wall-time budget exhausted; unfinished evidence is incomplete.')

    try:
        _acquire_worker(service, campaign_id, check)
        acquired = True
        started = time.monotonic()
        if runtime_binding() != request['binding']:
            raise ValueError('Source changed while queued; recreate the campaign.')
        total = cfg['budget_hours']*3600
        deadline = started+total-previous_elapsed
        check()
        state.update(status='running', phase='preflight')
        save()
        if 'pilot' not in report:
            report['pilot'] = preflight_and_pilot(folder, request, min(deadline,started+min(total*.1,cfg['pilot_seconds'])), check)
            report['preflight'] = report['pilot']['preflight']
            save()
        pilot = report['pilot']
        n_envs = pilot['n_envs']
        per_update = pilot['budget_update_seconds']
        trial_count = len(cfg['learning_rates'])+2
        initialization_budget = pilot.get('budget_initialization_seconds',0.)
        # Collection is already charged to elapsed pilot time. Reserve fitting for
        # every new model, and leave 30% of the original budget for comparisons.
        training_budget = min(total*.6, max(0.,deadline-time.monotonic()-total*.3))
        trial_deadline_seconds = state.get('trial_budget_seconds', training_budget/trial_count)
        affordable_updates = max(0, int((trial_deadline_seconds-initialization_budget)/per_update))
        updates = math.ceil(state['target_timesteps']/1024) if state.get('target_timesteps') else affordable_updates
        if cfg.get('training_timesteps') and not state.get('target_timesteps'):
            updates = math.ceil(cfg['training_timesteps']/1024)
        if updates < 8 or updates > affordable_updates:
            state.update(status='insufficient_throughput', phase='finished', error='Requested PPO updates and measured initialization do not fit the per-model budget (minimum eight updates). No training search claimed.')
            return
        target = updates*1024
        state.update(phase='learning_rate_screen', target_timesteps=target, selected_workers=n_envs,
                     trial_budget_seconds=trial_deadline_seconds, initialization_budget_seconds=initialization_budget)
        factory = FrozenEpisodeFactory(folder)
        validation = [(family, max(1,round(a['fleet_size']*.95))) for family,a in request['anchors'].items()]
        validation.extend((family,round(request.get('comparison_anchors',{}).get(family,a)['fleet_size']*1.05)) for family,a in request['anchors'].items())
        if cfg.get('target_fleet'):
            validation.append(('normal',cfg['target_fleet']))
        validation = sorted(set(validation))
        for index, rate in enumerate(cfg['learning_rates']):
            check()
            key = f'candidate-{index}'
            if any(r['key'] == key and r.get('status') == 'completed' and r.get('validation_complete') for r in report['trials']):
                continue
            out = folder/key
            last = out/'latest.json'
            result = train_policy(factory,out,target,learning_rate=rate,seed=cfg['initialization_seeds'][0],
                normalize_reward=cfg.get('normalize_reward',False), initial_log_std=cfg.get('initial_log_std',0.),
                llf_warmstart_episodes=cfg.get('llf_warmstart_episodes',0), llf_warmstart_epochs=cfg.get('llf_warmstart_epochs',30),
                n_envs=n_envs, binding=request['binding'], deadline=min(deadline,time.monotonic()+trial_deadline_seconds),
                progress=lambda _:save(), cancellation=lambda:(folder/'cancel').exists(), resume_from=last if last.exists() else None)
            row = {'key':key,'learning_rate':rate,**result}
            row['validation'] = []
            row['validation_complete'] = False
            if result.get('status') == 'completed':
                validation_ok = True
                for family,count in validation:
                    check()
                    evaluated = evaluate_policy(result['checkpoint'],FrozenEpisodeFactory(folder,'validation',(family,count)),
                        [0,1],deadline=deadline,cancellation=lambda:(folder/'cancel').exists(),binding=request['binding'])
                    row['validation'].extend(evaluated['episodes'])
                    if evaluated.get('status') != 'completed' or len(evaluated['episodes']) != 2:
                        validation_ok = False
                        break
                row['validation_complete'] = validation_ok and len(row['validation']) == 2*len(validation)
            report['trials'] = [r for r in report['trials'] if r['key'] != key]+[row]
            save()
            if result.get('status') == 'cancelled':
                raise InterruptedError('Training cancelled; committed checkpoints retained.')
            if result.get('status') == 'budget_exhausted':
                raise TimeoutError('Training or initialization budget exhausted; incomplete candidate retained.')
        eligible = [r for r in report['trials'] if r['key'].startswith('candidate-') and r.get('validation_complete') and _score(r.get('validation',[])) is not None]
        if len(eligible) != len(cfg['learning_rates']):
            raise RuntimeError('All configured candidates require complete equal-budget validation; no policy selected.')
        winner = min(eligible,key=lambda r:_score(r['validation']))
        report['validation_comparison'] = validation_baselines(folder,request,validation,report,deadline,check,save)
        for candidate in eligible:
            candidate['relative_validation'] = compare_validation(candidate['validation'],report['validation_comparison'])
        if any(set(c['relative_validation']) != set(BASELINES) or not all(v['complete_valid'] for v in c['relative_validation'].values()) for c in eligible):
            raise RuntimeError('Matched validation contains unknown or mismatched evidence; no comparative winner selected.')
        # Service/grid feasibility remain primary. Matched feasible peak differences break ties.
        def comparative_rank(candidate):
            relative=candidate['relative_validation']
            peak=sum(sum(r['feasible_peak_deltas_kw']) for r in relative.values() if r['complete_valid'])
            return (*_score(candidate['validation'])[:3],peak)
        winner=min(eligible,key=comparative_rank)
        report['selected_learning_rate'] = winner['learning_rate']
        state['phase'] = 'independent_seeds'
        for index, seed in enumerate(cfg['initialization_seeds'][1:],1):
            check()
            key = f'replicate-{index}'
            if any(r['key'] == key and r.get('status') == 'completed' for r in report['trials']):
                continue
            out = folder/key
            result = train_policy(factory,out,target,learning_rate=winner['learning_rate'],seed=seed,n_envs=n_envs,
                normalize_reward=cfg.get('normalize_reward',False), initial_log_std=cfg.get('initial_log_std',0.),
                llf_warmstart_episodes=cfg.get('llf_warmstart_episodes',0), llf_warmstart_epochs=cfg.get('llf_warmstart_epochs',30),
                binding=request['binding'],deadline=min(deadline,time.monotonic()+trial_deadline_seconds),
                progress=lambda _:save(), cancellation=lambda:(folder/'cancel').exists(),resume_from=out/'latest.json' if (out/'latest.json').exists() else None)
            report['trials'] = [r for r in report['trials'] if r['key'] != key]+[{'key':key,**result}]
            save()
            if result.get('status') == 'cancelled':
                raise InterruptedError('Training cancelled; committed checkpoints retained.')
            if result.get('status') == 'budget_exhausted':
                raise TimeoutError('Training or initialization budget exhausted; incomplete replicate retained.')
        state['phase'] = 'held_out_evaluation'
        selected = [winner]+[r for r in report['trials'] if r['key'].startswith('replicate-') and r.get('status') == 'completed']
        if len(selected) != 3:
            raise RuntimeError('Three completed independent training seeds are required before final evaluation.')
        evaluate_campaign(folder, request, selected, report, min(deadline,time.monotonic()+total*.2), check, save)
        if runtime_binding() != request['binding']:
            raise ValueError('Source changed during training; results are stale, not accepted.')
        report['summary'] = summarize_evaluation(report)
        normal = report['summary']['families'].get('normal',{})
        report['summary'].update(target_fleet=cfg['target_fleet'],
            target_met=None if cfg.get('target_fleet') is None else report['summary']['complete_valid_comparison'] and normal.get('ppo_tested_bound',0)>=cfg['target_fleet'])
        state.update(status='completed', phase='finished', scientific_verdict=report['summary']['verdict'],
                     selected_checkpoint=winner['checkpoint'])
    except InterruptedError as exc:
        state.update(status='cancelled',error=str(exc))
    except TimeoutError as exc:
        state.update(status='budget_exceeded',error=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        save()
        lock = service.root/'worker.lock'
        if acquired and lock.exists() and lock.read_text().strip() == campaign_id:
            lock.unlink(missing_ok=True)


def replay_benchmark_anchors(folder, request, deadline, check):
    """Replay every frozen anchor seed and verify its immutable demand/replay identity."""
    from .benchmark import trial_summary
    from .simulation import simulate_case
    from .continuous_env import ContinuousEVEnv
    fixture = read_json(Path(folder)/'fixtures.json')
    preflight = []
    def progress(_=None):
        check()
        if time.monotonic() >= deadline:
            raise TimeoutError('Benchmark parity preflight budget exhausted.')
    for family, anchor in request['anchors'].items():
        for seed in fixture['config']['seeds']:
            for count in dict.fromkeys((0, min(500,anchor['fleet_size']),anchor['fleet_size'])):
                progress()
                factory = FrozenEpisodeFactory(folder,'benchmark',(family,count))
                episode = factory(seed)
                if count == anchor['fleet_size']:
                    expected = next(t for t in anchor['evidence']['trials'] if t['seed'] == seed)
                    for key in ('demand_hash','replay_hash'):
                        if episode['metadata'][key] != expected[key]:
                            raise ValueError(f'Frozen benchmark {key} mismatch for {family}/{seed}.')
                strategy = anchor['strategy'] if count else 'immediate'
                raw = simulate_case({**episode['case'],'strategy':strategy},episode['demand_kw'],episode['sessions'],progress)
                outcome = trial_summary(raw)
                preflight.append(dict(**episode['metadata'],strategy=strategy,status=outcome['status'],metrics=outcome['metrics']))
                write_json(Path(folder)/'parity-evidence.json',preflight)
                if outcome['status'] != 'passed':
                    raise ValueError(f'Benchmark anchor replay failed for {family}/{count}/{seed}.')
                # The continuous all-on action must reproduce the benchmark immediate allocator.
                if count == min(500,anchor['fleet_size']):
                    immediate = trial_summary(simulate_case(episode['case'],episode['demand_kw'],episode['sessions'],progress))
                    env = ContinuousEVEnv(factory,sorted(b['id'] for b in fixture['blocks']))
                    env.configure_stop(deadline=deadline)
                    env.reset(seed=seed)
                    while not env._done:
                        progress()
                        env.step(np.ones(52,dtype=np.float32))
                    result = trial_summary(dict(complete=True,intervals=env.sim.intervals,metrics=env.episode_metrics))
                    for key in ('requested_energy_kwh','delivered_energy_kwh','unmet_energy_kwh','peak_demand_kw','min_voltage_pu'):
                        left,right=immediate['metrics'].get(key),result['metrics'].get(key)
                        if left is None or right is None or not math.isclose(left,right,rel_tol=1e-8,abs_tol=1e-5):
                            raise ValueError(f'Continuous all-demand parity failed: {family}/{seed}/{key}: {left} vs {right}')
                    if immediate['status'] != result['status']:
                        raise ValueError('Continuous and benchmark acceptance predicates disagree.')
                    preflight.append(dict(**episode['metadata'],strategy='continuous_all_demand',status='parity_verified'))
    return preflight


def preflight_and_pilot(folder, request, deadline, check):
    from .continuous_env import ContinuousEVEnv
    from .continuous_ppo import train_policy, _manifest
    from .benchmark import trial_summary
    from .simulation import simulate_case
    preflight = replay_benchmark_anchors(folder, request, deadline, check)
    timings = {}
    initialization_times = {}
    cfg = request.get('config',{})
    warmstart = cfg.get('llf_warmstart_episodes',0) > 0
    for workers in (1,2):
        check()
        timing_file = Path(folder)/f'pilot-{workers}'/'timing.json'
        if timing_file.exists():
            measured = read_json(timing_file)
            if warmstart and 'initialization_seconds' not in measured:
                raise ValueError('Pilot timing lacks warm-start overhead; recreate the campaign.')
            timings[workers] = measured['seconds']
            initialization_times[workers] = measured.get('initialization_seconds',0.)
            continue
        last = Path(folder)/f'pilot-{workers}'/'latest.json'
        target = (_manifest(last,request['binding'])['timesteps'] if last.exists() else 0)+1024
        began = time.monotonic()
        result = train_policy(FrozenEpisodeFactory(folder),Path(folder)/f'pilot-{workers}',target,
            normalize_reward=request.get('config',{}).get('normalize_reward',False), initial_log_std=request.get('config',{}).get('initial_log_std',0.),
            llf_warmstart_episodes=cfg.get('llf_warmstart_episodes',0), llf_warmstart_epochs=cfg.get('llf_warmstart_epochs',30),
            seed=7000,n_envs=workers,binding=request['binding'],deadline=deadline,
            resume_from=Path(folder)/f'pilot-{workers}'/'latest.json' if (Path(folder)/f'pilot-{workers}'/'latest.json').exists() else None,
            cancellation=lambda:(Path(folder)/'cancel').exists())
        if result.get('status') == 'cancelled':
            raise InterruptedError('Pilot initialization/training cancelled.')
        if result.get('status') != 'completed':
            raise TimeoutError('A complete initialized PPO throughput rollout did not fit the pilot budget.')
        measured = result.get('initialization_timing',{})
        timings[workers] = max(1e-9,time.monotonic()-began-sum(measured.values()))
        if warmstart:
            saved = Path(folder)/f'pilot-{workers}'/'initialization.json'
            initialization_times[workers] = measured.get('fitting_seconds',0.)
            if not initialization_times[workers] and saved.exists():
                initialization_times[workers] = read_json(saved).get('timing',{}).get('fitting_seconds',0.)
            if initialization_times[workers] <= 0:
                raise ValueError('Warm-start fitting time was not measured; no training budget accepted.')
        else:
            initialization_times[workers] = 0.
        write_json(timing_file,{'seconds':timings[workers], 'measured_transitions':1024,
                               'initialization_seconds':initialization_times[workers],
                               'collection_seconds':measured.get('collection_seconds',0.)})
    workers = 2 if timings[2] <= timings[1]/1.2 else 1
    # Single-rollout samples cannot estimate a p90: use a labeled conservative budget estimate.
    return dict(n_envs=workers,budget_update_seconds=timings[workers]*1.25,
                budget_initialization_seconds=max(initialization_times.values())*1.25,
                estimate_note='One initialized reset/rollout/update per worker count plus25% reserve; fitting is budgeted per model, collection is charged once in elapsed pilot time. Not an empirical p90.',
                timings=timings,preflight=preflight)


def evaluate_campaign(folder, request, selected, report, deadline, check, save):
    from .continuous_ppo import evaluate_policy
    from .benchmark import trial_summary
    from .simulation import simulate_case
    done = {r['block_id'] for r in report['evaluation'] if r.get('complete')}
    for family, anchor in request['anchors'].items():
        strongest = request.get('comparison_anchors',{}).get(family,anchor)['fleet_size']
        counts = sorted({max(1,round(anchor['fleet_size']*fraction)) for fraction in (.8,.95,1.,1.05)} | {strongest,max(1,round(strongest*1.05))})
        if family == 'normal' and request['config'].get('target_fleet'):
            counts = sorted(set(counts) | {request['config']['target_fleet'],round(request['config']['target_fleet']*1.05)})
        for count in counts:
            block_id = f'{family}-{count}'
            if block_id in done:
                continue
            block = dict(block_id=block_id,family=family,fleet_size=count,complete=False,policies=[])
            report['evaluation'] = [r for r in report['evaluation'] if r['block_id'] != block_id]
            report['evaluation'].append(block)
            factory = FrozenEpisodeFactory(folder,'test',(family,count))
            for policy in selected:
                check()
                result = evaluate_policy(policy['checkpoint'],factory,[0,1,2],deadline=deadline,
                    cancellation=lambda:(Path(folder)/'cancel').exists(),binding=request['binding'])
                block['policies'].append(dict(policy=policy['key'],**result))
                save()
                if result.get('status') != 'completed':
                    raise TimeoutError('Held-out block incomplete; do not compare partial policy evidence.')
            for strategy in BASELINES:
                trials = []
                for seed in (0,1,2):
                    check()
                    def progress(_):
                        check()
                        if time.monotonic() >= deadline:
                            raise TimeoutError('Held-out evaluation budget exhausted.')
                    e = factory(seed)
                    outcome = trial_summary(simulate_case({**e['case'],'strategy':'immediate' if strategy == 'all_demand' else strategy}, e['demand_kw'],e['sessions'],progress))
                    trials.append({**e['metadata'],**outcome})
                block['policies'].append(dict(policy=strategy,episodes=trials,status='completed'))
                save()
            block['complete'] = True
            save()


def summarize_evaluation(report):
    """Report tested bounds across all seeds, without extrapolating monotonic capacity."""
    families = {}
    paired_comparisons = []
    comparison_valid = bool(report['evaluation'])
    for block in report['evaluation']:
        if not block.get('complete'):
            comparison_valid = False
            continue
        names=[p['policy'] for p in block['policies']]
        if len(names)!=len(set(names)) or not set(BASELINES)<=set(names):
            comparison_valid=False
        references={p['policy']:p['episodes'] for p in block['policies'] if p['policy'] in BASELINES}
        for policy in block['policies']:
            if policy['policy'].startswith(('candidate-','replicate-')):
                paired_comparisons.append(dict(family=block['family'],fleet_size=block['fleet_size'],policy=policy['policy'],comparisons=compare_validation(policy['episodes'],references)))
        family = families.setdefault(block['family'], {'tested_bounds':{}, 'blocks':[]})
        policy_passes = []
        for policy in block['policies']:
            valid = policy.get('status') == 'completed' and len(policy['episodes']) == 3 and all(
                e.get('status') in ('passed','failed') if 'status' in e else e.get('metrics',e).get('complete',False) and not e.get('metrics',e).get('numerical_invalid',False)
                for e in policy['episodes'])
            comparison_valid = comparison_valid and valid
            passed = policy.get('status') == 'completed' and len(policy['episodes']) == 3 and all(
                e.get('status') == 'passed' or e.get('metrics',e).get('passed',False) for e in policy['episodes'])
            name = policy['policy']
            is_rl = name.startswith(('candidate-','replicate-'))
            if is_rl:
                policy_passes.append(passed)
            elif passed:
                family['tested_bounds'][name] = max(family['tested_bounds'].get(name,0),block['fleet_size'])
        rl_passed = len(policy_passes) == 3 and all(policy_passes)
        if rl_passed:
            family['tested_bounds']['node_ppo_all_training_seeds'] = max(family['tested_bounds'].get('node_ppo_all_training_seeds',0),block['fleet_size'])
        family['blocks'].append({'fleet_size':block['fleet_size'],'all_ppo_seeds_passed':rl_passed})
    if any(not all(c['complete_valid'] for c in row['comparisons'].values()) for row in paired_comparisons):
        comparison_valid=False
    for f in families.values():
        bounds=f['tested_bounds']
        f['best_baseline_bound']=max((bounds.get(s,0) for s in BASELINES),default=0)
        f['ppo_tested_bound']=bounds.get('node_ppo_all_training_seeds',0)
        f['capacity_improved']=f['ppo_tested_bound']>f['best_baseline_bound']
    if not comparison_valid:
        for f in families.values():
            f['capacity_improved'] = None
    improved=bool(families) and any(f['capacity_improved'] for f in families.values())
    no_regression=bool(families) and all(f['ppo_tested_bound']>=f['best_baseline_bound'] for f in families.values())
    no_regression = no_regression and all(c['feasibility_regressions']==0 for row in paired_comparisons for c in row['comparisons'].values())
    peak_evidence={}
    for name in BASELINES:
        values=[c['comparisons'][name] for c in paired_comparisons if name in c['comparisons']]
        deltas=[d for c in values for d in c['feasible_peak_relative_deltas']]
        peak_evidence[name]=dict(paired_feasible_cases=len(deltas),
            mean_relative_peak_change=sum(deltas)/len(deltas) if deltas else None,
            peak_improved_without_regression=bool(comparison_valid and deltas and all(d<=.001 for d in deltas) and any(d<-.001 for d in deltas) and all(c['feasibility_regressions']==0 for c in values)))
    return dict(verdict='inconclusive' if not comparison_valid else 'tested_capacity_improvement' if improved and no_regression else 'no_consistent_capacity_improvement',
                complete_valid_comparison=comparison_valid,
                paired_comparisons=paired_comparisons, feasible_peak_evidence=peak_evidence,
                objective='Outperform matched baseline policies; capacity and feasible peak are distinct outcomes.',
                families=families, limitation='Passing tested fleet bounds only; three held-out demand seeds per training seed. No monotonic feasibility or real-city capacity claim.',
                next_step='Preserve this held-out set. Any further tuning must use validation evidence and a fresh final-test seed range.')


if __name__ == '__main__':
    run_campaign(sys.argv[1],sys.argv[2])
