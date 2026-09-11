"""Continuous node budgets over the shared simulator; no grid rescue controller.

The deadline allocator and physical charger/energy caps are part of the environment.
Observations contain connected cohorts only. Snapshots are trusted local Python
objects (including the pandapower network), never a portable policy format.
"""
from __future__ import annotations

import copy
import math
import time
import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:
    raise ImportError('Continuous EV training requires gymnasium; install the project RL dependencies.') from exc

from .simulation import Simulator
from .network import build_network
from .districts import district_id
from .capacity_layers import capacity_layers

ENV_VERSION = 2
NODE_COUNT = 52
REWARD_FORMULA = ('delivered_battery_kwh/max(requested_battery_kwh,1) '
    '-20*new_departure_shortfall_kwh/max(requested_battery_kwh,1) '
    '-20*grid_severity -0.1*physical_cap_grid_kwh/max(requested_battery_kwh,1) '
    '-0.05*incremental_supply_peak_kw/reference_capacity_kw -20*numerical_invalid')
DEADLINE_HOURS = (1., 2., 4., 8., math.inf)
NODE_FEATURES = ('baseline_ratio', 'block_headroom', 'source_headroom',
                 'district_headroom', 'connected_power_ratio', 'remaining_energy_ratio',
                 'previous_power_ratio', 'connected', 'minimum_laxity', 'previous_voltage', 'voltage_valid',
                 'deadline_1_energy', 'deadline_1_power', 'deadline_2_energy',
                 'deadline_2_power', 'deadline_4_energy', 'deadline_4_power',
                 'deadline_8_energy', 'deadline_8_power', 'deadline_tail_energy',
                 'deadline_tail_power')
GLOBAL_FEATURES = ('clock_sin', 'clock_cos', 'horizon_remaining', 'stage_headroom', 'running_supply_peak')


def grid_severity(interval, limits):
    """One violation indicator plus deduplicated positive relative excesses."""
    unique = {(v.get('kind'), v.get('asset_type'), v.get('asset_id')): v
              for v in interval.get('violations', [])}
    total = float(bool(unique))
    for v in unique.values():
        value, limit = v.get('value'), v.get('limit')
        if value is not None and limit is not None and math.isfinite(value) and limit > 0:
            total += max(0., (limit-value if v.get('kind') == 'undervoltage' else value-limit)/limit)
    return total


class ContinuousStop(InterruptedError):
    def __init__(self, reason):
        self.stop_reason = reason
        super().__init__(reason)


class ContinuousEVEnv(gym.Env):
    """52 fixed node actions and causal, capacity-normalized observations.

    episode_factory(seed) returns case, demand_kw, sessions and optional metadata.
    Explicit reset seeds reproduce fixtures; unseeded resets draw a new seed from
    the environment RNG. Stateful factories may expose get_state/set_state.
    """
    metadata = {'render_modes': []}

    def __init__(self, episode_factory, node_ids=None):
        super().__init__()
        self.episode_factory = episode_factory
        node_ids = node_ids if node_ids is not None else getattr(episode_factory, 'node_ids', None)
        if node_ids is None:
            _, blocks = build_network()
            node_ids = sorted(b['id'] for b in blocks)
        self.node_ids = list(node_ids)
        if len(self.node_ids) != NODE_COUNT or len(set(self.node_ids)) != NODE_COUNT:
            raise ValueError('Continuous EV policy requires exactly 52 unique frozen node IDs.')
        self.action_space = spaces.Box(-1., 1., (NODE_COUNT,), dtype=np.float32)
        self.observation_space = spaces.Box(-10., 10.,
            (NODE_COUNT*len(NODE_FEATURES)+len(GLOBAL_FEATURES),), dtype=np.float32)
        self.sim = None
        self.episode_metrics = {}
        self._done = True
        self._deadline = None
        self._cancellation = None

    def configure_stop(self, deadline=None, cancellation=None):
        self._deadline, self._cancellation = deadline, cancellation

    def _check_stop(self, *_):
        cancel = self._cancellation
        if cancel is not None and (cancel() if callable(cancel) else cancel.is_set()):
            raise ContinuousStop('cancelled')
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise ContinuousStop('budget_exhausted')

    def reset(self, *, seed=None, options=None):
        self._check_stop()
        super().reset(seed=seed)
        episode_seed = int(seed if seed is not None else self.np_random.integers(0, 2**32-1))
        fixture = self.episode_factory(episode_seed)
        case = copy.deepcopy(fixture['case'])
        case.update(strategy='immediate', aggregate_ev_nodes=True, stop_on_violation=False)
        demand = fixture['demand_kw']
        if not demand or any(s['departure_step'] > len(demand) for s in fixture['sessions']):
            raise ValueError('Continuous episodes require a nonempty horizon covering every departure.')
        self.sim = Simulator()
        self.sim.reset(case, demand, fixture['sessions'], on_baseline_step=self._check_stop)
        self._check_stop()
        self.previous_voltages = self.sim.measure_baseline_voltages()
        self._check_stop()
        if set(self.sim.by_id) != set(self.node_ids):
            raise ValueError('Episode network nodes differ from the frozen policy node ordering.')
        self.episode_metadata = copy.deepcopy(fixture.get('metadata', {}))
        self.episode_seed = episode_seed
        self.previous_kw = np.zeros(NODE_COUNT)
        self.requested_energy = sum(s['energy_kwh'] for s in self.sim.sessions)
        self.energy_scale = max(self.requested_energy, 1.)
        self.reference_capacity = max(sum(d['capacity_kw'] for d in self.sim.resolved_districts), 1.)
        self.peak_kw = 0.
        self.charged_shortfall = 0.
        self.reward_total = 0.
        self._done = False
        self._invalid = False
        self._truncated = False
        self._started = time.perf_counter()
        self._elapsed_before = 0.
        self._max_steps = (options or {}).get('max_steps')
        if self._max_steps is not None and (isinstance(self._max_steps, bool)
                or not isinstance(self._max_steps, int) or self._max_steps < 1):
            raise ValueError('max_steps must be a positive integer.')
        self.episode_metrics = {}
        return self._observation(), {'episode_seed': episode_seed,
            'metadata': copy.deepcopy(self.episode_metadata), 'node_ids': self.node_ids.copy()}

    def _connected(self):
        return [s for s in self.sim.sessions if s['arrival_step'] <= self.sim.index < s['departure_step']]

    def _observation(self):
        sim = self.sim
        if sim.index >= len(sim.demand):
            return np.zeros(self.observation_space.shape, dtype=np.float32)
        baseline = {b['id']: (sim.case['block_demand_kw'][b['id']][sim.index]
                    if sim.case.get('block_demand_kw') else sim.demand[sim.index]*b['base_weight'])
                    for b in sim.blocks}
        source_load, district_load = {}, {}
        for b in sim.blocks:
            source_load[b['source_id']] = source_load.get(b['source_id'], 0.) + baseline[b['id']]
            key = district_id(b)
            district_load[key] = district_load.get(key, 0.) + baseline[b['id']]
        connected = {node: [] for node in self.node_ids}
        for s in self._connected():
            connected[s['block_id']].append(s)
        factor = sim.case.get('limits', {}).get('max_loading_percent', 100.)/100.
        rows = []
        for i, node in enumerate(self.node_ids):
            b = sim.by_id[node]
            scale = max(b['capacity_kw'], 1.)
            source_cap = max(b['source_capacity_kw'], 1.)
            district_cap = max(sim.district_by_id[district_id(b)]['capacity_kw'], 1.)
            sessions = connected[node]
            power = sum(s['charger_kw'] for s in sessions if s['remaining_kwh'] > 1e-9)
            remaining = sum(s['remaining_kwh'] for s in sessions)
            laxity = min(((s['departure_step']-sim.index)*sim.dt
                         - s['remaining_kwh']/(s['charger_kw']*s.get('efficiency', .9))
                         for s in sessions), default=0.)
            bins = np.zeros((len(DEADLINE_HOURS), 2))
            for s in sessions:
                hours = (s['departure_step']-sim.index)*sim.dt
                j = next(j for j, bound in enumerate(DEADLINE_HOURS) if hours <= bound)
                bins[j, 0] += s['remaining_kwh']/(scale*24.)
                bins[j, 1] += s['charger_kw']/scale if s['remaining_kwh'] > 1e-9 else 0.
            rows.extend([baseline[node]/scale, factor-baseline[node]/scale,
                         factor-source_load[b['source_id']]/source_cap,
                         1.-district_load[district_id(b)]/district_cap,
                         power/scale, remaining/(24.*scale), self.previous_kw[i]/scale,
                         float(bool(sessions)), laxity/24.,
                         self.previous_voltages.get(node, 1.), float(node in self.previous_voltages), *bins.ravel()])
        stages = capacity_layers(sim.net, sim.blocks, baseline, {n: 0. for n in self.node_ids},
                                 sim.case.get('network_capacity'))
        headroom = min((r['headroom_kw']/max(r['capacity_kw'], 1.) for r in stages), default=1.)
        phase = 2.*math.pi*((sim.index*sim.dt) % 24.)/24.
        rows.extend([math.sin(phase), math.cos(phase),
                     (len(sim.demand)-sim.index)/len(sim.demand), headroom,
                     self.peak_kw/self.reference_capacity])
        result = np.asarray(rows, dtype=np.float64)
        if not np.isfinite(result).all():
            raise FloatingPointError('Nonfinite continuous policy observation.')
        return np.clip(result, -10., 10.).astype(np.float32)

    def teacher_step(self, controller):
        """Collect an LLF demonstration, including its existing AC protection.

        Labels are executed node powers. PPO later uses the ordinary node allocator;
        imitation is therefore an initialization, not an exact LLF replacement.
        """
        actions = controller.actions(self.sim)
        charger = {n: 0. for n in self.node_ids}
        for s in self._connected():
            if s['remaining_kwh'] > 1e-9:
                charger[s['block_id']] += s['charger_kw']
        result = self.step(np.zeros(NODE_COUNT), _teacher_actions=actions)
        controller.observe(self.sim, self.sim.intervals[-1])
        executed = result[4]['continuous']['executed_node_kw']
        label = np.array([2.*executed[n]/charger[n]-1. if charger[n] else -1.
                          for n in self.node_ids], dtype=np.float32)
        return result, label, np.array([charger[n] > 0 for n in self.node_ids])

    def step(self, action, *, _teacher_actions=None):
        self._check_stop()
        if self._done:
            raise RuntimeError('Reset the environment before stepping a completed episode.')
        raw = np.asarray(action, dtype=np.float64)
        if raw.shape != (NODE_COUNT,) or not np.isfinite(raw).all():
            raise ValueError('Action must contain 52 finite node values.')
        bounded = np.clip(raw, -1., 1.)
        connected = self._connected()
        charger = {n: 0. for n in self.node_ids}
        physical = charger.copy()
        before_delivery = sum(s['delivered_kwh'] for s in self.sim.sessions)
        for s in connected:
            if s['remaining_kwh'] <= 1e-9:
                continue
            charger[s['block_id']] += s['charger_kw']
            physical[s['block_id']] += min(s['charger_kw'], s['remaining_kwh']/(self.sim.dt*s.get('efficiency', .9)))
        requested = {n: float((bounded[i]+1.)*.5*charger[n]) for i, n in enumerate(self.node_ids)}
        allocated = {n: min(requested[n], physical[n]) for n in self.node_ids}
        if _teacher_actions is None:
            _, interval, ended = self.sim.step_node_loads(requested)
        else:
            requested = {n: sum(_teacher_actions.get(s['id'], 0.) for s in connected
                                if s['block_id'] == n) for n in self.node_ids}
            allocated = {n: min(requested[n], physical[n]) for n in self.node_ids}
            previous_strategy = self.sim.case['strategy']
            try:
                self.sim.case['strategy'] = 'least_laxity_first'
                _, interval, ended = self.sim.step(_teacher_actions)
            finally:
                self.sim.case['strategy'] = previous_strategy
        executed = {n: 0. for n in self.node_ids}
        for s in self.sim.sessions:
            executed[s['block_id']] += interval['applied_actions_kw'].get(s['id'], 0.)
        self.previous_kw = np.array([executed[n] for n in self.node_ids])
        self.previous_voltages = {b['id']:float(self.sim.net.res_bus.at[b['bus_index'],'vm_pu'])
            for b in self.sim.blocks if interval.get('converged') and math.isfinite(float(self.sim.net.res_bus.at[b['bus_index'],'vm_pu']))}
        self._invalid = not bool(interval.get('converged', False))
        supplied = interval.get('supply_kw')
        if supplied is None or not math.isfinite(supplied):
            self._invalid = True
        delivery = sum(s['delivered_kwh'] for s in self.sim.sessions)-before_delivery
        shortfall = sum(s['remaining_kwh'] for s in self.sim.sessions
                        if s['departure_step'] <= self.sim.index)
        new_shortfall = max(0., shortfall-self.charged_shortfall)
        self.charged_shortfall = shortfall
        severity = grid_severity(interval, self.sim.case.get('limits', {}))
        increment_peak = max(0., supplied-self.peak_kw) if not self._invalid else 0.
        if not self._invalid:
            self.peak_kw = max(self.peak_kw, supplied)
        capped_kwh = sum(max(0., requested[n]-allocated[n]) for n in self.node_ids)*self.sim.dt
        terms = {'delivery': delivery/self.energy_scale,
                 'shortfall': -20.*new_shortfall/self.energy_scale,
                 'grid': -20.*severity,
                 'physical_cap': -.1*capped_kwh/self.energy_scale,
                 'peak': -.05*increment_peak/self.reference_capacity,
                 'numerical_failure': -20. if self._invalid else 0.}
        reward = float(sum(terms.values()))
        self.reward_total += reward
        natural = self.sim.index >= len(self.sim.demand)
        self._truncated = bool(self._max_steps is not None and self.sim.index >= self._max_steps and not natural)
        # Numerical failure is an invalid terminal sample, never success or a
        # time-limit bootstrap into the invalid power-flow state.
        terminated = bool(natural or self._invalid)
        truncated = bool(self._truncated and not terminated)
        self._done = terminated or truncated
        diagnostics = {'raw_action': raw.tolist(), 'bounded_action': bounded.tolist(),
                       'requested_node_kw': requested, 'allocated_node_kw': allocated,
                       'executed_node_kw': executed, 'physical_cap_kwh': capped_kwh,
                       'reward_terms': terms, 'grid_rescue_enabled': _teacher_actions is not None}
        interval['continuous'] = diagnostics
        self.episode_metrics = self._metrics(natural and not self._invalid and not truncated)
        info = {'continuous': diagnostics, 'numerical_invalid': self._invalid,
                'episode_seed': self.episode_seed, 'episode_metrics': copy.deepcopy(self.episode_metrics)}
        observation = np.zeros(self.observation_space.shape, dtype=np.float32) if self._invalid else self._observation()
        return observation, reward, terminated, truncated, info

    def _metrics(self, complete):
        intervals = self.sim.intervals
        unmet = sum(s['remaining_kwh'] for s in self.sim.sessions if s['departure_step'] <= self.sim.index)
        pending = sum(s['remaining_kwh'] for s in self.sim.sessions if s['departure_step'] > self.sim.index)
        violations = sum(bool(i.get('violations')) for i in intervals)
        nonconverged = sum(not i.get('converged', False) for i in intervals)
        def extreme(key, function=max):
            values = [i[key] for i in intervals if i.get(key) is not None and math.isfinite(i[key])]
            return function(values) if values else None
        delivered = sum(s['delivered_kwh'] for s in self.sim.sessions)
        energy_ok = unmet <= 1e-5 and pending <= 1e-5 and abs(self.requested_energy-delivered-unmet) <= 1e-5
        return {'complete': bool(complete), 'passed': bool(complete and not violations and not nonconverged and energy_ok),
                'episode_metadata': copy.deepcopy(self.episode_metadata),
                'numerical_invalid': self._invalid, 'truncated': self._truncated,
                'violation_intervals': violations, 'nonconverged_steps': nonconverged,
                'unmet_energy_kwh': unmet, 'pending_energy_kwh': pending,
                'requested_energy_kwh': self.requested_energy,
                'delivered_energy_kwh': sum(s['delivered_kwh'] for s in self.sim.sessions),
                'peak_demand_kw': extreme('supply_kw'), 'supply_peak_kw': extreme('supply_kw'),
                'load_peak_kw': extreme('total_kw'), 'min_voltage_pu': extreme('min_voltage_pu', min),
                'max_line_loading_percent': extreme('max_line_loading_percent'),
                'max_transformer_loading_percent': extreme('max_transformer_loading_percent'),
                'max_voltage_pu': extreme('max_voltage_pu'),
                'max_network_capacity_loading_percent': extreme('max_network_capacity_loading_percent'),
                'max_district_loading_percent': extreme('max_district_loading_percent'),
                'voltage_violation_steps': sum(any(v['kind'] in ('undervoltage', 'overvoltage')
                    for v in i.get('violations', [])) for i in intervals),
                'overload_steps': sum(any(v['kind'] in ('line_overload', 'transformer_overload')
                    for v in i.get('violations', [])) for i in intervals),
                'network_capacity_overload_steps': sum(any(v['kind'] == 'network_capacity_exceeded'
                    for v in i.get('violations', [])) for i in intervals),
                'district_overload_steps': sum(any(v['kind'] == 'district_capacity_exceeded'
                    for v in i.get('violations', [])) for i in intervals),
                'physical_cap_kwh': sum(i.get('continuous', {}).get('physical_cap_kwh', 0.) for i in intervals),
                'grid_ev_energy_kwh': sum(sum(i.get('applied_actions_kw', {}).values())*self.sim.dt for i in intervals),
                'reward_components': {name: sum(i.get('continuous', {}).get('reward_terms', {}).get(name, 0.)
                    for i in intervals) for name in ('delivery', 'shortfall', 'grid', 'physical_cap', 'peak', 'numerical_failure')},
                'reward': self.reward_total, 'steps': self.sim.index,
                'vehicle_count': self.sim.vehicle_count,
                'runtime_seconds': self._elapsed_before+time.perf_counter()-self._started}

    def get_state(self):
        if self.sim is None:
            raise RuntimeError('Cannot checkpoint an environment before reset.')
        fields = ('episode_metadata', 'episode_seed', 'previous_kw', 'previous_voltages', 'requested_energy',
                  'energy_scale', 'reference_capacity', 'peak_kw', 'charged_shortfall',
                  'reward_total', '_done', '_invalid', '_truncated', '_max_steps', 'episode_metrics')
        return copy.deepcopy({'version': ENV_VERSION, 'node_ids': self.node_ids,
            'sim': self.sim.__dict__, 'fields': {k: getattr(self, k) for k in fields},
            'rng': self.np_random.bit_generator.state,
            'elapsed': self._elapsed_before+time.perf_counter()-self._started,
            'factory_state': self.episode_factory.get_state() if hasattr(self.episode_factory, 'get_state') else None})

    def set_state(self, state):
        state = copy.deepcopy(state)
        if state['version'] != ENV_VERSION or state['node_ids'] != self.node_ids:
            raise ValueError('Environment checkpoint version/node ordering mismatch.')
        self.sim = Simulator()
        self.sim.__dict__.update(state['sim'])
        for k, v in state['fields'].items():
            setattr(self, k, v)
        self.np_random.bit_generator.state = state['rng']
        self._elapsed_before = state['elapsed']
        self._started = time.perf_counter()
        if state.get('factory_state') is not None:
            if not hasattr(self.episode_factory, 'set_state'):
                raise ValueError('Checkpoint requires a stateful episode factory.')
            self.episode_factory.set_state(state['factory_state'])
