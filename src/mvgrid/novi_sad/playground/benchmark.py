"""Versioned, replay-frozen ten-scenario benchmarks using the shared simulator.

Capacity is the largest passing *tested* fleet, never an assumed monotone binary
search or a real-city hosting limit. Every seed must pass complete departures.
"""
from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import uuid
from typing import Literal
from datetime import datetime, timezone

import pandapower as pp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mvgrid.paths import REPOSITORY_ROOT
from .service import Service, digest, read_json, write_json, implementation_fingerprint
from .schema import DemandConfig, NetworkCapacity, Limits
from .strategies import StrategyOptions, strategy_catalog
from .network import build_network
from .districts import resolve_districts, district_id
from .demand import generate_demand, allocate_block_demand
from .simulation import simulate_case
from .operating_scenario import apply_network_scenario, apply_demand_scenario
from .charging_profiles import visits, PROFILE_VERSION, PROFILE_DESCRIPTIONS

PROTOCOL = 'novi-sad-benchmark-v1'
TESTS = [
    dict(id='common', title='Shared passing fleet', kind='common', scenario='normal', description='Largest tested fleet up to the reference size that every selected algorithm serves.'),
    dict(id='winter', title='Winter · fixed fleet', kind='fixed', scenario='winter', description='January demand, identical reference fleet.'),
    dict(id='winter_worst', title='Worst winter · fixed fleet', kind='fixed', scenario='worst', description='January demand +20%, identical reference fleet.'),
    dict(id='summer_worst', title='Worst summer · fixed fleet', kind='fixed', scenario='summer_worst', description='June demand +20%, identical reference fleet.'),
    dict(id='synchronized', title='Synchronized arrivals', kind='fixed', scenario='synchronized', description='All EVs arrive at 18:00; reference fleet on a normal day.'),
    dict(id='district', title='One district · fixed fleet', kind='fixed', scenario='district', description='All EVs in the frozen busiest district, reference fleet.'),
    dict(id='city_max', title='Citywide capacity · normal', kind='capacity', scenario='normal', description='Scan the same increasing fleet ladder on a normal June day.'),
    dict(id='city_worst_max', title='Citywide capacity · worst', kind='capacity', scenario='worst', description='Scan the fleet ladder on a +20% January day.'),
    dict(id='district_max', title='District capacity · normal', kind='capacity', scenario='district', description='Scan the ladder with all EVs in one district.'),
    dict(id='district_worst_max', title='District capacity · worst', kind='capacity', scenario='district_worst', description='Concentrated EVs and +20% January demand.'),
]


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    name: str = Field(default='Novi Sad · standard 10', min_length=1, max_length=100)
    standard_fleet: int = Field(default=100, ge=1, le=50000)
    max_fleet: int = Field(default=10000, ge=1, le=50000)
    seeds: list[int] = Field(default_factory=lambda: [41001, 41002, 41003], min_length=1, max_length=5)
    district: str | None = None
    operating_mode: Literal['as_supplied','regulated'] = 'as_supplied'
    search_mode: Literal['refined','doubling'] = 'refined'
    until_failure: bool = False
    aggregate_ev_nodes: bool = False
    charging_profile: Literal['home_only','whole_day'] = 'home_only'

    @model_validator(mode='after')
    def bounds(self):
        if self.until_failure and self.search_mode != 'doubling':
            raise ValueError('Uncapped search requires doubling mode.')
        if not self.until_failure and self.max_fleet < self.standard_fleet:
            raise ValueError('Maximum fleet must be at least the reference fleet.')
        if len(set(self.seeds)) != len(self.seeds) or any(s < 0 or s > 4294967295 for s in self.seeds):
            raise ValueError('Seeds must be unique unsigned 32-bit integers.')
        return self


class BenchmarkRunConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    strategies: list[str] = Field(min_length=1, max_length=100)
    model_id: str | None = None
    strategy_options: StrategyOptions = Field(default_factory=StrategyOptions)
    max_runtime_seconds: float = Field(default=3600, ge=1, le=43200, allow_inf_nan=False)
    case_runtime_seconds: float = Field(default=120, ge=1, le=3600, allow_inf_nan=False)


def fleet_ladder(config):
    if config.get('until_failure'):
        return [0, 2]
    if config.get('search_mode') == 'doubling':
        values = [0]
        n = 2
        while n <= config['max_fleet']:
            values.append(n)
            n *= 2
        return values
    values = {0, 1, config['standard_fleet'], config['max_fleet']}
    n = config['standard_fleet']
    while n < config['max_fleet']:
        values.add(n)
        n *= 2
    return sorted(values)


def capacity_counts(fixture):
    """Lazy, unbounded powers of two; the evaluator stops on fail/unknown."""
    if fixture['config'].get('until_failure'):
        yield 0
        n = 2
        while True:
            yield n
            n *= 2
    else:
        yield from fixture['ladder']


def common_ladder(config):
    values = {1, config['standard_fleet']}
    n = config['standard_fleet']
    while n > 1:
        values.add(n)
        n //= 2
    return sorted(values, reverse=True)


def session_pool(blocks, seed, size, district=None, synchronized=False, charging_profile='home_only'):
    """Nested fleets: each vehicle has its own seed; IDs sort in vehicle order.

    Overnight residential benchmark, 14 battery kWh at 7.4 kW / 90% efficiency.
    All depart at 09:00, allowing even the latest delayed release to meet demand
    when unconstrained. No charging model is given realized future arrivals.
    """
    if charging_profile == 'whole_day':
        return visits(blocks,seed,size,'whole_day',district_mix={district:1.} if district else None,synchronized=synchronized)
    if charging_profile != 'home_only': raise ValueError('Unknown benchmark charging profile')
    candidates = sorted((b for b in blocks if b.get('kind') != 'public_hub' and
                         (district is None or district_id(b) == district)), key=lambda b: b['id'])
    if not candidates:
        raise ValueError('District has no residential charging blocks.')
    weights = [max(float(b['base_weight']), 0.) for b in candidates]
    if not sum(weights):
        weights = [1.] * len(candidates)
    rows = []
    for i in range(size):
        rng = random.Random(f'{PROTOCOL}:{seed}:{i}')
        block = rng.choices(candidates, weights=weights)[0]
        arrival = rng.randrange(68, 85)
        rows.append(dict(id=f'benchmark-{i:06d}', block_id=block['id'], district_id=district_id(block),
                         arrival_step=72 if synchronized else arrival, departure_step=132,
                         energy_kwh=14., charger_kw=7.4, efficiency=.9, location_type='residential'))
    return rows


def trial_summary(result):
    metrics = dict(result.get('metrics', {}))
    intervals = result.get('intervals', [])
    complete = bool(result.get('complete')) and len(intervals) == 132
    violations = sum(bool(i.get('violations')) for i in intervals)
    valid = complete and all(i.get('converged') for i in intervals) and bool(metrics)
    requested = metrics.get('requested_energy_kwh')
    delivered = metrics.get('delivered_energy_kwh')
    unmet = metrics.get('unmet_energy_kwh')
    energy_ok = all(v is not None for v in (requested, delivered, unmet)) and (
        unmet <= 1e-5 and metrics.get('pending_energy_kwh', 0.) <= 1e-5 and abs(requested-delivered-unmet) <= 1e-5)
    passed = valid and not violations and energy_ok
    reasons = []
    if not complete: reasons.append('incomplete departure coverage')
    if not valid: reasons.append('electrical evidence unavailable')
    if violations:
        details=[]
        if metrics.get('voltage_violation_steps',0): details.append('voltage limit')
        if metrics.get('overload_steps',0): details.append('line/transformer loading')
        if metrics.get('network_capacity_overload_steps',0): details.append('aggregate capacity')
        if metrics.get('district_overload_steps',0): details.append('district capacity')
        reasons.append('grid limit violation'+(': '+', '.join(details) if details else ''))
    if not energy_ok: reasons.append('departure energy unmet or unverified')
    stages = [s for i in intervals for s in i.get('capacity_layers', [])]
    districts = [d for i in intervals for d in i.get('districts', [])]
    headroom = [s['headroom_kw'] for s in stages if s.get('headroom_kw') is not None]
    def maximum(key):
        values = [s[key] for s in stages if s.get(key) is not None]
        return max(values) if values else None
    stage_loading = maximum('loading_percent')
    district_loading = max((d['loading_percent'] for d in districts), default=None)
    metrics.update(violation_intervals=violations,
                   min_stage_headroom_kw=min(headroom) if valid and headroom else None,
                   spare_stage_percent=100-stage_loading if valid and stage_loading is not None else None,
                   spare_district_percent=100-district_loading if valid and district_loading is not None else None,
                   min_district_headroom_kw=min((d['headroom_kw'] for d in districts), default=None) if valid else None,
                   safety_intervals=sum(i.get('safety_iterations', 0) > 0 for i in intervals),
                   fallback_intervals=sum(bool(i.get('controller', {}).get('fallback')) for i in intervals),
                   optimizer_limit_intervals=sum(i.get('controller', {}).get('solver_status') == 'odc_iteration_limit' for i in intervals),
                   curtailed_grid_energy_kwh=sum(i.get('curtailed_ev_kw', 0.)*.25 for i in intervals))
    return dict(status='passed' if passed else 'failed' if valid else 'incomplete', complete=complete,
                reasons=reasons, metrics=metrics,
                trace=[dict(step=i['step'], total_kw=i['total_kw'], ev_kw=i['ev_kw'],
                            min_voltage_pu=i.get('min_voltage_pu'), violations=len(i.get('violations', []))) for i in intervals])


def aggregate_trials(trials):
    if not trials:
        return dict(status='incomplete', metrics={}, reasons=['not evaluated'])
    status = ('incomplete' if any(t['status'] in ('incomplete', 'error') for t in trials) else
              'failed' if any(t['status'] != 'passed' for t in trials) else 'passed')
    keys = set().union(*(t.get('metrics', {}).keys() for t in trials))
    minimum = {'delivered_energy_kwh', 'min_voltage_pu', 'min_stage_headroom_kw', 'spare_stage_percent',
               'spare_district_percent', 'min_district_headroom_kw'}
    metrics = {}
    for key in keys:
        values = [t.get('metrics', {}).get(key) for t in trials]
        if any(v is None for v in values): metrics[key] = None
        else: metrics[key] = min(values) if key in minimum else max(values)
    return dict(status=status, metrics=metrics, reasons=sorted({r for t in trials for r in t.get('reasons', [])}))


def refine_capacity_boundary(attempts, evaluate):
    """Measure adjacent integer outcomes; never turn unknowns into failures."""
    passing=[a['fleet_size'] for a in attempts if a['status']=='passed']
    if not passing: return
    low=max(passing)
    failing=[a['fleet_size'] for a in attempts if a['status']=='failed' and a['fleet_size']>low]
    if not failing: return
    high=min(failing)
    while high-low>1:
        result=evaluate((low+high)//2)
        attempts.append(result)
        if result['status']=='passed': low=result['fleet_size']
        elif result['status']=='failed': high=result['fleet_size']
        else: break
    attempts.sort(key=lambda a:a['fleet_size'])


class BenchmarkService:
    def __init__(self, root=None):
        self.service = Service(root)
        self.root = self.service.root

    def path(self, category, identifier):
        return self.service._path(category, identifier)

    def catalog(self):
        _, blocks = build_network()
        return dict(protocol=PROTOCOL, tests=TESTS, defaults=BenchmarkConfig().model_dump(), charging_profiles=PROFILE_DESCRIPTIONS,
                    run_defaults=BenchmarkRunConfig(strategies=['immediate', 'capacity_aware']).model_dump(),
                    strategies=strategy_catalog(), districts=resolve_districts(blocks),
                    suites=[read_json(p) for p in sorted((self.root/'benchmark-suites').glob('*/summary.json'))],
                    jobs=[self.get_job(p.parent.name) for p in sorted((self.root/'benchmarks').glob('*/state.json'),
                                                                    key=lambda p: p.stat().st_mtime, reverse=True)])

    def create_suite(self, definition):
        cfg = BenchmarkConfig.model_validate(definition).model_dump()
        net, blocks = build_network()
        apply_network_scenario(net,cfg['operating_mode'])
        districts = resolve_districts(blocks)
        profiles = {}
        for name, month, energy, days, worst in [('normal', 6, 76000, 30, False), ('winter', 1, 120000, 31, False),
                                               ('worst', 1, 120000, 31, True), ('summer_worst', 6, 76000, 30, True)]:
            demand = DemandConfig(month=month, monthly_energy=energy, days_per_month=days, days=2,
                                  scenario='worst_case' if worst else 'base')
            profiles[name] = apply_demand_scenario(generate_demand(demand),cfg['operating_mode'])[:132]
        distribution = allocate_block_demand(profiles['normal'], blocks, {})
        # Select once from exogenous normal baseline, not a candidate's result.
        busiest = max(districts, key=lambda d: (max(sum(distribution[b][t] for b in d['block_ids']) for t in range(132))/d['capacity_kw'], d['id']))['id']
        cfg['district'] = cfg['district'] or busiest
        if cfg['district'] not in {d['id'] for d in districts}:
            raise ValueError('Unknown benchmark district.')
        pools = {f'{mode}-{seed}': session_pool(blocks, seed, cfg['standard_fleet'] if cfg.get('until_failure') else cfg['max_fleet'],
                    cfg['district'] if mode == 'district' else None, mode == 'synchronized',cfg['charging_profile'])
                 for mode in ('city', 'district', 'synchronized') for seed in cfg['seeds']}
        tests=copy.deepcopy(TESTS)
        if cfg['charging_profile']=='whole_day':
            for test in tests:
                test['description']='Whole-day mixed charging. '+test['description']
                if test['id']=='synchronized':
                    test.update(title='Synchronized by location',description='Whole-day mix: home arrivals 18:00, workplace 08:00, public 12:00; normal departure rules retained.')
        network_text = pp.to_json(net)
        frozen = dict(protocol=PROTOCOL, config=cfg, tests=tests, blocks=blocks, districts=districts,
                      charging_profile_version=PROFILE_VERSION if cfg['charging_profile']=='whole_day' else 'overnight-v1',
                      charging_profile_description=PROFILE_DESCRIPTIONS[cfg['charging_profile']],
                      demand_measurement='supply_including_losses',
                      demand=profiles, pools=pools, network_hash=hashlib.sha256(network_text.encode()).hexdigest(),
                      limits=Limits().model_dump(), network_capacity=NetworkCapacity().model_dump(),
                      ladder=fleet_ladder(cfg), common_ladder=common_ladder(cfg))
        suite_id = 'suite-'+digest(frozen)[:20]
        folder = self.path('benchmark-suites', suite_id)
        summary = dict(suite_id=suite_id, protocol=PROTOCOL, config=cfg, tests=tests, ladder=frozen['ladder'],
                       charging_profile_description=frozen['charging_profile_description'],
                       demand_measurement=frozen['demand_measurement'],
                       common_ladder=frozen['common_ladder'], fixture_hash=digest(frozen))
        if not (folder/'summary.json').exists():
            folder.mkdir(parents=True, exist_ok=True)
            (folder/'network.json').write_bytes(network_text.encode('utf-8'))
            write_json(folder/'fixtures.json', frozen)
            write_json(folder/'summary.json', summary)
        return summary

    def get_suite(self, suite_id):
        folder = self.path('benchmark-suites', suite_id)
        summary = read_json(folder/'summary.json')
        fixtures = read_json(folder/'fixtures.json')
        if digest(fixtures) != summary['fixture_hash'] or hashlib.sha256((folder/'network.json').read_bytes()).hexdigest() != fixtures['network_hash']:
            raise ValueError('Frozen benchmark fixtures changed; create a new suite.')
        if fixtures['config'].get('charging_profile') == 'whole_day' and fixtures.get('charging_profile_version') != PROFILE_VERSION:
            raise ValueError('Charging profile version changed; create a new benchmark suite.')
        return fixtures

    def start(self, suite_id, config):
        broker = os.environ.get('EV_PLAYGROUND_BROKER_URL')
        if broker:
            from urllib.parse import urlsplit
            from urllib.request import Request, urlopen
            import json
            parsed = urlsplit(broker)
            if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.path not in ('', '/'):
                raise ValueError('Benchmark broker must be a loopback HTTP origin.')
            body = json.dumps(dict(suite_id=suite_id, config=config, runtime_root=str(self.root))).encode()
            with urlopen(Request(broker.rstrip('/')+'/api/benchmarks/jobs', data=body, headers={'Content-Type':'application/json'}), timeout=30) as response:
                return json.load(response)
        cfg = BenchmarkRunConfig.model_validate(config).model_dump(mode='json')
        available = {s['id'] for s in strategy_catalog()}
        if len(set(cfg['strategies'])) != len(cfg['strategies']) or not set(cfg['strategies']) <= available:
            raise ValueError('Choose distinct registered algorithms; new algorithms appear after registration.')
        fixtures = self.get_suite(suite_id)
        if fixtures['config'].get('aggregate_ev_nodes') and 'rl' in cfg['strategies']:
            raise ValueError('Node aggregation supports continuous load control; use individual mode for binary per-car RL.')
        frozen_model = None
        if 'rl' in cfg['strategies']:
            if not cfg['model_id']: raise ValueError('Select a frozen RL model before benchmarking RL.')
            from .rl_service import RLService
            frozen_model = RLService(self.root).get_model(cfg['model_id'])
            if set(fixtures['config']['seeds']) & set(frozen_model['payload']['training_seeds']):
                raise ValueError('Benchmark seeds overlap RL training seeds. Create a held-out suite.')
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root/'worker.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            active = lock.read_text().strip()
            if not active or self.service.get_run(active)['status'] in ('starting', 'running'):
                raise ValueError('A worker is active; wait or cancel it before starting the benchmark.')
            lock.unlink()
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        job_id = 'bench-'+uuid.uuid4().hex[:16]
        folder = self.path('benchmarks', job_id)
        try:
            os.write(fd, job_id.encode()); os.close(fd); fd = None
            fingerprint = implementation_fingerprint()
            request = dict(suite_id=suite_id, config=cfg, model=frozen_model, fingerprint=fingerprint,
                           implementation_id=digest(fingerprint)[:12])
            write_json(folder/'request.json', request)
            state = dict(job_id=job_id, suite_id=suite_id, status='starting', pid=None, completed_rows=0,
                         total_rows=len(fixtures['tests'])*len(cfg['strategies']), strategies=cfg['strategies'],
                         created_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=0.,
                         implementation_id=request['implementation_id'])
            write_json(folder/'state.json', state)
            write_json(folder/'results.json', dict(rows=[], common_fleet=None, complete=False))
            with open(folder/'worker.log', 'a', encoding='utf-8') as log:
                process = subprocess.Popen([sys.executable, '-m', 'mvgrid.novi_sad.playground.benchmark', str(self.root), job_id],
                    cwd=str(REPOSITORY_ROOT), env=dict(os.environ, PYTHONPATH=str(REPOSITORY_ROOT/'src')),
                    stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            state['pid'] = process.pid
            write_json(folder/'state.json', state)
            return state
        except Exception:
            if fd is not None: os.close(fd)
            lock.unlink(missing_ok=True)
            raise

    def get_job(self, job_id):
        folder = self.path('benchmarks', job_id)
        state = read_json(folder/'state.json')
        if state['status'] in ('starting', 'running'):
            import psutil
            if (state.get('pid') and not psutil.pid_exists(state['pid'])) or (not state.get('pid') and time.time()-(folder/'state.json').stat().st_mtime > 30):
                state.update(status='interrupted', error='Worker exited before completion.')
                write_json(folder/'state.json', state)
        return state

    def results(self, job_id):
        folder = self.path('benchmarks', job_id)
        return dict(job=self.get_job(job_id), request=read_json(folder/'request.json'), **read_json(folder/'results.json'))

    def cancel(self, job_id):
        state = self.get_job(job_id)
        if state['status'] in ('starting', 'running'):
            (self.path('benchmarks', job_id)/'cancel').touch()
        return dict(job_id=job_id, cancel_requested=state['status'] in ('starting', 'running'))

    def comparison(self, suite_id):
        # Only completed jobs share the leaderboard; partial jobs remain inspectable.
        self.get_suite(suite_id)
        rows = []
        for path in sorted((self.root/'benchmarks').glob('*/state.json'), key=lambda p: p.stat().st_mtime):
            state = self.get_job(path.parent.name)
            if state['suite_id'] != suite_id or state['status'] != 'completed': continue
            data = self.results(state['job_id'])
            candidate = digest(dict(implementation=state['implementation_id'], config={k:v for k,v in data['request']['config'].items()
                               if k not in ('strategies', 'max_runtime_seconds', 'case_runtime_seconds')}))[:12]
            # Common fleet depends on the selected cohort; never merge it across jobs.
            rows.extend(dict(row, job_id=state['job_id'], candidate_id=candidate,
                             implementation_id=state['implementation_id']) for row in data['rows'] if row['test_id'] != 'common')
        latest = {(r['strategy'], r['candidate_id'], r['test_id']): r for r in rows}
        return dict(suite_id=suite_id, rows=list(latest.values()), note='Same frozen fixtures; separate implementation/settings versions. Shared-fleet comparisons are within one job only.')


def run_benchmark(root, job_id):
    service = BenchmarkService(root)
    folder = service.path('benchmarks', job_id)
    state = read_json(folder/'state.json')
    for _ in range(100):
        if state.get('pid'): break
        time.sleep(.05); state = read_json(folder/'state.json')
    started = time.perf_counter()
    request = read_json(folder/'request.json')
    cfg = request['config']
    rows, cache = [], {}
    common_fleet = None
    state.update(status='running', error=None)
    def save():
        state.update(elapsed_seconds=time.perf_counter()-started, completed_rows=len(rows))
        write_json(folder/'results.json', dict(rows=rows, common_fleet=common_fleet, complete=state['status']=='completed'))
        write_json(folder/'state.json', state)
    def check():
        if (folder/'cancel').exists(): raise InterruptedError('Benchmark cancelled; unfinished cells are not passes.')
        if time.perf_counter()-started > cfg['max_runtime_seconds']: raise TimeoutError('Benchmark runtime limit reached.')
    try:
        fixture = service.get_suite(request['suite_id'])
        if request['fingerprint'] != implementation_fingerprint(): raise ValueError('Implementation changed before the benchmark started.')
        suite_folder = service.path('benchmark-suites', request['suite_id'])
        def evaluate(scenario, strategy, count):
            key = (scenario, strategy, count)
            if key in cache: return copy.deepcopy(cache[key])
            trials = []
            profile_name = 'worst' if scenario == 'district_worst' else 'normal' if scenario in ('district', 'synchronized') else scenario
            profile = fixture['demand'][profile_name]
            mode = 'district' if scenario.startswith('district') else 'synchronized' if scenario == 'synchronized' else 'city'
            for seed in fixture['config']['seeds']:
                check()
                state.update(current_strategy=strategy, current_fleet=count, current_seed=seed, current_step=0)
                save()
                trial_started = time.perf_counter()
                def progress(interval):
                    check()
                    if time.perf_counter()-trial_started > cfg['case_runtime_seconds']:
                        raise RuntimeError('Per-case runtime limit reached; capacity unknown for this trial.')
                    if interval['step'] % 8 == 0:
                        state.update(current_step=interval['step']+1); save()
                sessions = fixture['pools'][f'{mode}-{seed}'][:count]
                if len(sessions) < count:
                    if not fixture['config'].get('until_failure'):
                        raise ValueError('Requested fleet exceeds frozen pool.')
                    sessions = session_pool(fixture['blocks'], seed, count,
                        fixture['config']['district'] if mode == 'district' else None, mode == 'synchronized',fixture['config'].get('charging_profile','home_only'))
                    prefix=fixture['pools'][f'{mode}-{seed}']
                    if sessions[:len(prefix)] != prefix:
                        raise ValueError('Charging session generator changed; create a new benchmark suite.')
                options = dict(strategy=strategy, seed=seed, limits=fixture['limits'], stop_on_violation=False,
                               aggregate_ev_nodes=fixture['config'].get('aggregate_ev_nodes',False),
                               demand_measurement=fixture.get('demand_measurement','load'),
                               fixed_start_hour=23, strategy_options=cfg['strategy_options'],
                               network_path=str(suite_folder/'network.json'), blocks=fixture['blocks'],
                               resolved_districts=fixture['districts'], network_capacity=fixture['network_capacity'],
                               block_demand_kw=allocate_block_demand(profile, fixture['blocks'], {}))
                if strategy == 'rl':
                    # Benchmark fixes shield on and no energy budget for all comparisons.
                    options.update(rl=dict(model_id=cfg['model_id'], safety_shield=True), rl_policy=request['model']['payload']['policy'])
                try:
                    outcome = trial_summary(simulate_case(options, profile, sessions, progress))
                except (InterruptedError, TimeoutError): raise
                except Exception as exc:
                    outcome = dict(status='error', complete=False, reasons=[f'{type(exc).__name__}: {exc}'], metrics={}, trace=[])
                outcome.update(seed=seed, fleet_size=count, demand_hash=digest(profile), replay_hash=digest(sessions))
                trial_id = digest(dict(scenario=scenario, strategy=strategy, count=count, seed=seed))[:20]
                write_json(folder/'trials'/(trial_id+'.json'), outcome)
                trials.append(outcome)
            aggregate = aggregate_trials(trials)
            aggregate.update(fleet_size=count, trials=[dict(seed=t['seed'], status=t['status'], demand_hash=t['demand_hash'], replay_hash=t['replay_hash']) for t in trials])
            cache[key] = aggregate
            return copy.deepcopy(aggregate)

        for test in fixture['tests']:
            state['current_test'] = test['id']; save()
            if test['kind'] == 'common':
                history = {s: [] for s in cfg['strategies']}
                for count in fixture['common_ladder']:
                    evaluations = {s: evaluate('normal', s, count) for s in cfg['strategies']}
                    for s, value in evaluations.items(): history[s].append(value)
                    if all(v['status'] == 'passed' for v in evaluations.values()):
                        common_fleet = count; break
                for strategy in cfg['strategies']:
                    result = history[strategy][-1]
                    unresolved = any(v['status'] in ('error', 'incomplete') for values in history.values() for v in values)
                    rows.append(dict(test_id=test['id'], strategy=strategy, kind='common', status='passed' if common_fleet else 'incomplete' if unresolved else 'no_common_fleet',
                                     fleet_size=common_fleet, metrics=result['metrics'] if common_fleet else {}, attempts=history[strategy],
                                     note='All selected algorithms pass all seeds at this fleet.' if common_fleet else 'No positive shared passing fleet found on the tested ladder.'))
                save(); continue
            for strategy in cfg['strategies']:
                check()
                if test['kind'] == 'fixed':
                    baseline = evaluate(test['scenario'], strategy, 0)
                    result = evaluate(test['scenario'], strategy, fixture['config']['standard_fleet'])
                    rows.append(dict(test_id=test['id'], strategy=strategy, kind='fixed', baseline=baseline, **result))
                else:
                    attempts = []
                    for count in capacity_counts(fixture):
                        result = evaluate(test['scenario'], strategy, count)
                        attempts.append(result)
                        if fixture['config'].get('search_mode') == 'doubling' and result['status'] != 'passed':
                            break
                    # Refine the uppermost observed passing-to-failing bracket.
                    # This is a local boundary, not a proof of global monotonicity.
                    first_doubling_failure = next((a['fleet_size'] for a in attempts if a['fleet_size']>0 and a['status']=='failed'),None)
                    if fixture['config'].get('search_mode') != 'doubling' or fixture['config'].get('until_failure'):
                        refine_capacity_boundary(attempts, lambda n: evaluate(test['scenario'], strategy, n))
                    passed = [a for a in attempts if a['status'] == 'passed']
                    best = max(passed, key=lambda a:a['fleet_size']) if passed else None
                    uncertain = any(a['status'] in ('incomplete', 'error') for a in attempts)
                    baseline_failed = attempts[0]['status'] == 'failed'
                    status = ('incomplete' if uncertain else 'baseline_limited' if baseline_failed and not passed else
                              'ceiling_reached' if not fixture['config'].get('until_failure') and best and best['fleet_size'] == fixture['ladder'][-1] else 'bounded')
                    rows.append(dict(test_id=test['id'], strategy=strategy, kind='capacity', status=status,
                                     fleet_size=best['fleet_size'] if best else None, metrics=best['metrics'] if best else attempts[0]['metrics'],
                                     attempts=attempts, first_failed_fleet=min((a['fleet_size'] for a in attempts if a['status']=='failed'), default=None),
                                     next_failed_fleet=min((a['fleet_size'] for a in attempts if best and a['status']=='failed' and a['fleet_size']>best['fleet_size']),default=None),
                                     baseline=attempts[0],
                                     search_mode=fixture['config'].get('search_mode','refined'),
                                     first_failed_doubling=first_doubling_failure if fixture['config'].get('search_mode')=='doubling' else None,
                                     additional_cars_vs_common=max(0, best['fleet_size']-common_fleet) if best and common_fleet is not None else None,
                                     note='Uncapped doubling brackets the first failure, then refines the observed transition to adjacent car counts when evidence is available. This is a local tested boundary, not proof of global monotonicity.' if fixture['config'].get('until_failure') else 'Doubling search stops at the first failure or unknown trial; the last pass and first fail bracket the observed transition, not an exact maximum.' if fixture['config'].get('search_mode')=='doubling' else 'Largest passing tested fleet; upper passing/failing bracket refined to one car where available. Untested intervals may contain other feasible counts; no global monotonicity claim.'))
                save()
        if request['fingerprint'] != implementation_fingerprint(): raise ValueError('Implementation changed during benchmark; start a fresh run.')
        state['status'] = 'completed'
    except InterruptedError as exc: state.update(status='cancelled', error=str(exc))
    except TimeoutError as exc: state.update(status='budget_exceeded', error=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        save()
        lock = service.root/'worker.lock'
        if lock.exists() and lock.read_text().strip() == job_id: lock.unlink(missing_ok=True)


if __name__ == '__main__':
    run_benchmark(sys.argv[1], sys.argv[2])
