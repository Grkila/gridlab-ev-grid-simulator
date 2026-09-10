"""Centralized binary charging policy and auditable episodic policy-gradient learning.

One shared neural actor observes city/grid context plus each connected session.
Its joint action is a vector of Bernoulli switches, not a power modulation.
Only NumPy is required. This is REINFORCE, not PPO or a pretrained optimal policy.
"""
from __future__ import annotations

import math
import numpy as np
from .capacity_layers import capacity_layers, ev_stage_fraction
from .districts import district_id
from .schema import RewardWeights

FEATURE_VERSION = 1
FEATURES = ['remaining_fraction', 'hours_left', 'required_fraction', 'slack',
            'baseline_ratio', 'district_ratio', 'source_ratio', 'block_ratio',
            'stage_headroom', 'clock_sin', 'clock_cos', 'previous_on',
            'connected_power_ratio', 'urgency_pressure', 'energy_headroom', 'charger_ratio']


def current_baseline(sim):
    t = sim.index
    return {b['id']:float(sim.case['block_demand_kw'][b['id']][t])
            if sim.case.get('block_demand_kw') else sim.demand[t]*b['base_weight'] for b in sim.blocks}


def features(sim, previous=None, energy_used=0., energy_limit=None):
    """Current observations only; future demand and arrivals are never actor inputs."""
    previous = previous or {}
    connected = sorted((s for s in sim.observation()['sessions'] if s['remaining_kwh'] > 1e-8), key=lambda s:str(s['id']))
    baseline = current_baseline(sim)
    total_capacity = max(sum(d['capacity_kw'] for d in sim.resolved_districts), 1.)
    total = sum(baseline.values())
    district_load = {d['id']:sum(baseline[b] for b in d['block_ids']) for d in sim.resolved_districts}
    source_load = {}
    for b in sim.blocks:
        source_load[b['source_id']] = source_load.get(b['source_id'], 0.) + baseline[b['id']]
    stages = capacity_layers(sim.net, sim.blocks, baseline, {b['id']:0. for b in sim.blocks}, sim.case.get('network_capacity'))
    headroom = min((r['headroom_kw']/r['capacity_kw'] for r in stages), default=1.)
    connected_power = sum(s['charger_kw'] for s in connected)/total_capacity
    phase = 2*math.pi*(sim.index*sim.dt % 24)/24
    rows = []
    for s in connected:
        b = sim.by_id[s['block_id']]
        d = district_id(b)
        hours = (s['departure_step']-sim.index)*sim.dt
        need = s['remaining_kwh']/(s['charger_kw']*s.get('efficiency', .9))
        ratio = district_load[d]/sim.district_by_id[d]['capacity_kw']
        rows.append([s['remaining_kwh']/max(s['energy_kwh'],1e-9), hours/24,
                     need/max(hours,sim.dt), (hours-need)/24, total/total_capacity,
                     ratio, source_load[b['source_id']]/max(b['source_capacity_kw'],1.),
                     baseline[b['id']]/max(b['capacity_kw'],1.), headroom,
                     math.sin(phase),math.cos(phase),float(previous.get(s['id'],False)),
                     connected_power, ratio*need/max(hours,sim.dt),
                     (energy_limit-energy_used)/energy_limit if energy_limit else 1.,
                     s['charger_kw']/max(b['capacity_kw'],1.)])
    return connected, np.clip(np.asarray(rows,dtype=float).reshape(-1,len(FEATURES)), -10, 10)


class BinaryPolicy:
    def __init__(self, seed=0, weights=None):
        rng = np.random.default_rng(seed)
        self.weights = {k:np.asarray(v,dtype=float) for k,v in weights.items()} if weights else {
            'w1':rng.normal(0,.15,(len(FEATURES),24)), 'b1':np.zeros(24),
            'w2':rng.normal(0,.15,24), 'b2':np.zeros(1)}
        shapes = {'w1':(len(FEATURES),24),'b1':(24,),'w2':(24,),'b2':(1,)}
        if set(self.weights)!=set(shapes) or any(self.weights[k].shape!=v or not np.isfinite(self.weights[k]).all() for k,v in shapes.items()):
            raise ValueError('Invalid policy weights')
        self.baseline = None

    def probabilities(self, x):
        h = np.tanh(x@self.weights['w1']+self.weights['b1'])
        logits = np.clip(h@self.weights['w2']+self.weights['b2'][0],-20,20)
        return 1/(1+np.exp(-logits))

    def predict(self, x, rng=None):
        p = self.probabilities(x)
        return ((rng.random(len(p)) < p) if rng is not None else (p >= .5)).astype(int), p

    def to_dict(self):
        return {'algorithm':'centralized-bernoulli-reinforce', 'feature_version':FEATURE_VERSION,
                'features':FEATURES, 'weights':{k:v.tolist() for k,v in self.weights.items()}}

    @classmethod
    def from_dict(cls, data):
        if data.get('feature_version') != FEATURE_VERSION or data.get('features') != FEATURES or data.get('algorithm')!='centralized-bernoulli-reinforce':
            raise ValueError('Unsupported policy feature/algorithm version')
        return cls(weights=data['weights'])

    def update(self, trajectory, learning_rate=.01, gamma=.99):
        """REINFORCE with previous-episode time baselines and bounded gradient norm.

        Trajectory entries contain x/actions/probabilities/reward. The score is for
        requested switches, including shielded proposals; no gradient is fabricated
        from the executed action. Running baselines never use this episode first.
        """
        if not trajectory: return 0.
        returns = np.zeros(len(trajectory)); running = 0.
        for t in range(len(trajectory)-1,-1,-1):
            running = float(trajectory[t]['reward'])+gamma*running
            returns[t] = running
        baseline = np.zeros(len(returns))
        if self.baseline is not None:
            n = min(len(returns),len(self.baseline)); baseline[:n] = self.baseline[:n]
        advantage = (returns-baseline)/max(float(np.std(returns-baseline)),1.)
        gradients = {k:np.zeros_like(v) for k,v in self.weights.items()}
        for item, adv in zip(trajectory,advantage):
            x = item['x']; residual = (item['actions']-item['probabilities'])*adv
            h = np.tanh(x@self.weights['w1']+self.weights['b1'])
            gradients['w2'] += h.T@residual
            gradients['b2'][0] += residual.sum()
            dh = residual[:,None]*self.weights['w2'][None,:]*(1-h*h)
            gradients['w1'] += x.T@dh
            gradients['b1'] += dh.sum(axis=0)
        gradients = {k:v/len(trajectory) for k,v in gradients.items()}
        norm = math.sqrt(sum(float(np.sum(v*v)) for v in gradients.values()))
        for k,g in gradients.items(): self.weights[k] += learning_rate*g*min(1.,10/max(norm,1e-12))
        self.baseline = .9*baseline+.1*returns
        if any(not np.isfinite(v).all() for v in self.weights.values()): raise ValueError('Training produced nonfinite weights')
        return norm


def shield_actions(sim, actions, probabilities=None, energy_remaining=None):
    """Binary admission by urgency under shared block, source, district and stage budgets.

    AC checks and additional binary removals happen in Simulator.step. An unsafe
    baseline remains visible: turning off all chargers cannot fix baseline demand.
    """
    baseline = current_baseline(sim)
    factor = sim.case.get('limits',{}).get('max_loading_percent',100)/100
    block_left = {b['id']:max(0.,b['capacity_kw']*factor-baseline[b['id']]) for b in sim.blocks}
    source_left = {}
    district_left = {d['id']:d['capacity_kw']-sum(baseline[b] for b in d['block_ids']) for d in sim.resolved_districts}
    for b in sim.blocks:
        source_left.setdefault(b['source_id'],b['source_capacity_kw']*factor)
        source_left[b['source_id']] -= baseline[b['id']]
    stages = capacity_layers(sim.net,sim.blocks,baseline,{b['id']:0. for b in sim.blocks},sim.case.get('network_capacity'))
    stage_left = {r['id']:r['headroom_kw'] for r in stages}
    remaining_kw = max(0.,energy_remaining/sim.dt-sum(baseline.values())) if energy_remaining is not None else math.inf
    result = {}
    sessions = sim.observation()['sessions']
    def priority(s):
        laxity = (s['departure_step']-sim.index)*sim.dt-s['remaining_kwh']/(s['charger_kw']*s.get('efficiency',.9))
        return laxity,-(probabilities or {}).get(s['id'],0),str(s['id'])
    for s in sorted(sessions,key=priority):
        power = float(actions.get(s['id'],0.))
        b = sim.by_id[s['block_id']]; d = district_id(b)
        allowed = min(block_left[b['id']],max(0.,source_left[b['source_id']]),max(0.,district_left[d]),remaining_kw)
        for stage,left in stage_left.items():
            share = ev_stage_fraction(stage,b,sim.case.get('network_capacity'))
            if share: allowed = min(allowed,max(0.,left)/share)
        power = power if power <= allowed+1e-9 else 0.
        result[s['id']] = power
        block_left[b['id']] -= power; source_left[b['source_id']] -= power; district_left[d] -= power; remaining_kw -= power
        for stage in stage_left: stage_left[stage] -= power*ev_stage_fraction(stage,b,sim.case.get('network_capacity'))
    return result


def reward_signal(interval, sessions, dt, weights=None, switches=0, interventions=0,
                  energy_before=0., energy_limit=None, energy_scale=None, fleet_scale=None):
    weights = RewardWeights.model_validate(weights or {}).model_dump()
    scale = max(float(energy_scale if energy_scale is not None else sum(s['energy_kwh'] for s in sessions)),1.)
    count = max(int(fleet_scale if fleet_scale is not None else len(sessions)),1)
    # Deduplicate upstream violations repeated once for each affected demand block.
    unique = {(v['kind'],v.get('asset_type'),v.get('asset_id')):v for v in interval['violations'] if v['kind']!='daily_energy_exceeded'}
    severity = 0.
    for v in unique.values():
        value,limit = v.get('value'),v.get('limit')
        if value is not None and limit: severity = max(severity,abs(value-limit)/abs(limit))
    departure_shortfall = sum(s['remaining_kwh'] for s in sessions if s['departure_step']==interval['step']+1)
    efficiency = {s['id']:s.get('efficiency',.9) for s in sessions}
    delivered = sum(v['power_kw']*dt*efficiency[v['id']]
                    for b in interval['blocks'] for v in b['vehicles'] if v['power_kw']>0)
    after = energy_before+interval['total_kw']*dt
    excess = max(0.,after-energy_limit)-max(0.,energy_before-energy_limit) if energy_limit else 0.
    capacity = sum(d['capacity_kw'] for d in interval['districts']) or 1.
    raw = {'delivery':delivered/scale,'shortfall':-departure_shortfall/scale,
           'capacity':-(1+severity) if unique else 0.,
           'energy':-(1+excess/energy_limit) if energy_limit and after>energy_limit+1e-9 else 0.,
           'switching':-switches/count, 'peak':-(interval['total_kw']/capacity)**2,
           'intervention':-interventions/count}
    components = {k:float(raw[k]*weights[k]) for k in raw}
    return {'reward':sum(components.values()),'components':components,'energy_excess_kwh':excess}


class RLController:
    def __init__(self, policy, config=None, seed=None, training=False):
        self.policy = policy; self.config = config or {}; self.training = training
        self.rng = np.random.default_rng(seed) if training else None
        self.previous = {}; self.energy_used = 0.; self.day = None; self.trajectory = []

    def actions(self, sim):
        day = int(sim.index*sim.dt//24)
        if self.day != day: self.day = day; self.energy_used = 0.
        limit = self.config.get('daily_energy_limit_kwh')
        sessions,x = features(sim,self.previous,self.energy_used,limit)
        actions,p = self.policy.predict(x,self.rng)
        requested = {s['id']:min(s['charger_kw'],s['remaining_kwh']/(sim.dt*s.get('efficiency',.9)))*int(a) for s,a in zip(sessions,actions)}
        proposed = shield_actions(sim,requested,dict(zip((s['id'] for s in sessions),p)),limit-self.energy_used if limit else None) if self.config.get('safety_shield',True) else requested
        self.pending = {'x':x,'actions':actions,'probabilities':p,'requested':requested}
        return proposed

    def observe(self, sim, interval):
        actual = {v['id']:v['power_kw']>1e-9 for b in interval['blocks'] for v in b['vehicles']}
        requested = self.pending['requested']
        interval['requested_ev_kw'] = sum(requested.values())
        interval['curtailed_ev_kw'] = max(0.,sum(requested.values())-interval['ev_kw'])
        # Arrival is not a switch from a previous controlled state; departure likewise.
        switches = sum(on != self.previous[k] for k,on in actual.items() if k in self.previous)
        interventions = sum(p>1e-9 and not actual.get(k,False) for k,p in requested.items())
        reward = reward_signal(interval,sim.sessions,sim.dt,self.config.get('reward'),switches,interventions,self.energy_used,self.config.get('daily_energy_limit_kwh'))
        interval['rl'] = {**reward,'requested_on':sum(p>1e-9 for p in requested.values()),
                          'executed_on':sum(actual.values()),'switches':switches,'interventions':interventions,
                          'daily_energy_kwh':self.energy_used+interval['total_kw']*sim.dt}
        self.energy_used += interval['total_kw']*sim.dt
        self.previous = actual
        if self.training: self.trajectory.append({**self.pending,'reward':reward['reward']})
        return interval['rl']
