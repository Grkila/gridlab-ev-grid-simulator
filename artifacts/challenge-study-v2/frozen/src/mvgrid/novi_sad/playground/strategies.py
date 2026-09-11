"""Research-inspired continuous charging controllers with causal observations.

These are planning-model adaptations, not reproductions of the cited algorithms.
All controllers implement actions(sim) and observe(sim, interval), like the RL adapter.
"""
from __future__ import annotations

import math
import time
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

NEW_STRATEGIES = ('least_laxity_first', 'valley_filling', 'mpc', 'voltage_responsive')


class StrategyOptions(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    horizon_steps: int = Field(default=96, ge=1, le=192)
    forecast: Literal['persistence', 'previous_day'] = 'persistence'
    valley_iterations: int = Field(default=8, ge=1, le=50)
    max_variables: int = Field(default=30000, ge=100, le=100000)
    solver_seconds: float = Field(default=3., gt=0, le=30, allow_inf_nan=False)
    voltage_stop_pu: float = Field(default=.95, gt=0, le=1.1, allow_inf_nan=False)
    voltage_full_pu: float = Field(default=.99, gt=0, le=1.2, allow_inf_nan=False)
    recovery_fraction: float = Field(default=.25, gt=0, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def voltage_order(self):
        if self.voltage_stop_pu >= self.voltage_full_pu:
            raise ValueError('voltage_stop_pu must be below voltage_full_pu')
        return self


def strategy_catalog():
    rows = [
        ('immediate', 'Immediate', 'baseline', 'Charge at available charger power.', None),
        ('fixed_delay', 'Fixed delay', 'baseline', 'Wait until the configured start hour.', None),
        ('randomized_delay', 'Randomized delay', 'baseline', 'Stagger starts using seeded delays.', None),
        ('capacity_aware', 'Capacity aware', 'heuristic', 'Departure-first allocation within capacity budgets and AC checks.', None),
        ('least_laxity_first', 'Smoothed least laxity first', 'optimization', 'Optimize next-step laxity smoothing within current linear grid budgets.', 'https://arxiv.org/abs/2102.08610'),
        ('valley_filling', 'Valley filling (ODC)', 'optimization', 'Simultaneous proximal ODC updates flatten forecast demand for connected sessions.', 'https://smart.caltech.edu/papers/ContinuousEVCharging.pdf'),
        ('mpc', 'Model predictive control', 'optimization', 'Re-solve a capacity-constrained linear program; prioritize energy delivery, then peak.', 'https://ieeexplore.ieee.org/document/9409126'),
        ('voltage_responsive', 'Voltage droop heuristic', 'local_feedback', 'Use causal block voltage with gradual recovery and mandatory central protection.', 'https://www.sciencedirect.com/science/article/pii/S0378779618301020'),
        ('rl', 'Learned on/off policy', 'reinforcement_learning', 'A frozen trained model chooses per-session on/off actions.', None),
    ]
    return [dict(id=key, label=label, family=family, description=description,
                 research_url=url, implementation='planning-model adaptation' if key in NEW_STRATEGIES else 'existing controller',
                 action_space='binary_on_off' if key == 'rl' else 'continuous_kw',
                 observations='previous measured block voltage' if key == 'voltage_responsive' else 'current connected sessions and grid state',
                 forecast='explicit causal persistence or previous-day baseline; no future arrivals' if key in ('mpc','valley_filling') else 'none',
                 limitation='Custom droop, not the cited historical three-phase algorithm. Balanced MV voltage and mandatory central shield; full paper algorithm unverified.' if key == 'voltage_responsive' else
                 'Generalized constrained smoothing; numerical failure falls back to plain LLF. Paper feasibility theorems are not established for this grid.' if key == 'least_laxity_first' else
                 'Full connected-departure linear forecast with plain LLF resource fallback; ASA phase, pilot, tariff and BMS mechanisms absent.' if key == 'mpc' else
                 'Finite ODC iterations with convergence diagnostics; current action projected to capacity budgets; online forecast adaptation.' if key == 'valley_filling' else
                 'Custom REINFORCE prototype, not EV-GNN or DeepTOP. Training completion does not validate policy quality.' if key == 'rl' else
                 'Uncoordinated reference policy; no automatic grid safety reduction or paper-reproduction claim.' if key in ('immediate','fixed_delay','randomized_delay') else
                 'Custom departure-priority heuristic with centralized protection, not a paper algorithm or feasibility guarantee.')
            for key,label,family,description,url in rows]


def baseline_at(sim, step):
    return {b['id']:float(sim.case['block_demand_kw'][b['id']][step]) if sim.case.get('block_demand_kw')
            else float(sim.demand[step])*b['base_weight'] for b in sim.blocks}


def connected_sessions(sim):
    return sorted((s for s in sim.observation()['sessions'] if s['remaining_kwh'] > 1e-8), key=lambda s:str(s['id']))


def slack(s, sim):
    return (s['departure_step']-sim.index)*sim.dt-s['remaining_kwh']/(s['charger_kw']*s.get('efficiency',.9))


def capacity_constraints(sim, baseline, sessions):
    """Return (session coefficients, nonnegative remaining kW) for known budgets.

    A baseline overload leaves zero EV headroom; it is still reported by power flow.
    AC voltage, reactive demand and losses are handled by the simulator, not this LP.
    """
    from .capacity_layers import capacity_layers, ev_stage_fraction
    from .districts import district_id
    rows = []
    factor = sim.case.get('limits',{}).get('max_loading_percent',100)/100
    def add(members, budget, coefficients=None):
        weights = np.array([float(s['block_id'] in members) for s in sessions]) if coefficients is None else coefficients
        if np.any(weights): rows.append((weights, max(0.,float(budget))))
    for b in sim.blocks:
        add({b['id']},b['capacity_kw']*factor-baseline[b['id']])
    for source in sorted({b['source_id'] for b in sim.blocks}):
        blocks = [b for b in sim.blocks if b['source_id']==source]
        add({b['id'] for b in blocks},blocks[0]['source_capacity_kw']*factor-sum(baseline[b['id']] for b in blocks))
    for d in sim.resolved_districts:
        members = {b['id'] for b in sim.blocks if district_id(b)==d['id']}
        add(members,d['capacity_kw']-sum(baseline[b] for b in members))
    for stage in capacity_layers(sim.net,sim.blocks,baseline,{b['id']:0. for b in sim.blocks},sim.case.get('network_capacity')):
        weights=np.array([ev_stage_fraction(stage['id'],sim.by_id[s['block_id']],sim.case.get('network_capacity')) for s in sessions])
        add(set(),stage['headroom_kw'],weights)
    return rows


def project_headroom(sim, sessions, requested):
    rows=capacity_constraints(sim,baseline_at(sim,sim.index),sessions)
    budgets=[budget for _,budget in rows]
    actions={}
    order=sorted(range(len(sessions)),key=lambda i:(slack(sessions[i],sim),sessions[i]['departure_step'],str(sessions[i]['id'])))
    for i in order:
        s=sessions[i]
        power=min(max(0.,float(requested.get(s['id'],0.))),s['charger_kw'],s['remaining_kwh']/(sim.dt*s.get('efficiency',.9)))
        for j,(weights,_) in enumerate(rows):
            if weights[i]>0: power=min(power,budgets[j]/weights[i])
        power=max(0.,power)
        actions[s['id']]=power
        for j,(weights,_) in enumerate(rows): budgets[j]=max(0.,budgets[j]-power*weights[i])
    return actions


class ChargingController:
    def __init__(self,name,options=None):
        if name not in NEW_STRATEGIES: raise ValueError(f'Unknown continuous strategy: {name}')
        self.name=name
        self.options=StrategyOptions.model_validate(options or {})
        self.voltages={}
        self.voltage_initialized=False
        self.previous={}
        self.last={}

    def forecast(self,sim,horizon):
        now=baseline_at(sim,sim.index)
        day=max(1,round(24/sim.dt))
        history=sim.intervals
        profiles=[]
        for offset in range(horizon):
            index=sim.index+offset-day
            # Read observed history only. Longer horizons fall back to persistence.
            if offset>0 and self.options.forecast=='previous_day' and 0<=index<len(history):
                past={b['id']:b['baseline_kw'] for b in history[index]['blocks']}
                profiles.append({key:past.get(key,value) for key,value in now.items()})
            else: profiles.append(dict(now))
        return profiles

    def actions(self,sim):
        started=time.perf_counter()
        sessions=connected_sessions(sim)
        self.last=dict(strategy=self.name,forecast=self.options.forecast if self.name in ('mpc','valley_filling') else 'none',
                       fallback=None, solver_status=None, predicted_shortfall_kwh=0.,
                       shortfall_scope='horizon-required battery energy; not a forecast of final departure shortfall')
        raw={s['id']:s['charger_kw'] for s in sessions}
        smoothed_feasible=False
        if sessions:
            if self.name=='least_laxity_first':
                from .smoothed_llf import allocate
                try:
                    raw,diagnostics=allocate(sessions,sim.index,sim.dt,
                        capacity_constraints(sim,baseline_at(sim,sim.index),sessions),
                        seconds=self.options.solver_seconds,max_variables=self.options.max_variables)
                    self.last.update(diagnostics)
                    smoothed_feasible=True
                except (RuntimeError, ValueError, ImportError, FloatingPointError, TimeoutError) as exc:
                    self.last.update(fallback=f'plain_least_laxity_first: {exc}',
                                     solver_status='smoothed_llf_failed',method='plain_llf_fallback')
            elif self.name in ('mpc','valley_filling'):
                departure_horizon=max(s['departure_step']-sim.index for s in sessions)
                # Individual charger capacity beyond a truncated horizon cannot
                # certify that shared network capacity can serve those EVs.
                horizon=departure_horizon
                self.last.update(requested_horizon_steps=self.options.horizon_steps,
                                 effective_horizon_steps=horizon,
                                 horizon_extended=horizon>self.options.horizon_steps)
                variables=len(sessions)*horizon+(len(sessions)+1 if self.name=='mpc' else 0)
                self.last['optimization_variables']=variables
                if variables>self.options.max_variables:
                    self.last['fallback']='plain_least_laxity_first: variable budget exceeded'
                else:
                    profiles=self.forecast(sim,horizon)
                    raw=self._mpc(sim,sessions,profiles) if self.name=='mpc' else self._valley(sim,sessions,profiles)
            elif self.name=='voltage_responsive':
                if not self.voltage_initialized and not self.voltages:
                    measure=getattr(sim,'measure_baseline_voltages',None)
                    self.voltages=measure() if measure else {}
                    self.voltage_initialized=True
                    self.last['voltage_bootstrap']='baseline_measurement' if self.voltages else 'measurement_unavailable'
                self.last['safety_overlay']='mandatory centralized capacity and AC shield'
                raw={}
                for s in sessions:
                    voltage=self.voltages.get(s['block_id'])
                    fraction=0. if voltage is None else min(1.,max(0.,(voltage-self.options.voltage_stop_pu)/(self.options.voltage_full_pu-self.options.voltage_stop_pu)))
                    target=s['charger_kw']*fraction
                    raw[s['id']]=min(target,self.previous.get(s['id'],0.)+s['charger_kw']*self.options.recovery_fraction*sim.dt/.25)
        raw={s['id']:min(max(0.,float(raw.get(s['id'],0.))),s['charger_kw'],s['remaining_kwh']/(sim.dt*s.get('efficiency',.9))) for s in sessions}
        # Voltage policy is local here; the simulator always applies its central shield.
        result=raw if self.name=='voltage_responsive' or smoothed_feasible else project_headroom(sim,sessions,raw)
        self.last.update(requested_kw=sum(raw.values()),allocated_kw=sum(result.values()),
                         headroom_curtailed_kw=max(0.,sum(raw.values())-sum(result.values())),
                         decision_seconds=time.perf_counter()-started)
        return result

    def _valley(self,sim,sessions,profiles):
        from .valley_odc import solve_odc
        h=len(profiles)
        upper=np.zeros((len(sessions),h))
        energy=[]
        deficit=0.
        required=0.
        for i,s in enumerate(sessions):
            available=min(h,s['departure_step']-sim.index)
            efficiency=s.get('efficiency',.9)
            target=s['remaining_kwh']
            attainable=min(target,available*s['charger_kw']*sim.dt*efficiency)
            required+=target
            deficit+=target-attainable
            upper[i,:available]=s['charger_kw']
            energy.append(attainable/(sim.dt*efficiency))
        schedule,diagnostics=solve_odc([sum(p.values()) for p in profiles],upper,energy,self.options.valley_iterations)
        self.last.update(diagnostics,predicted_shortfall_kwh=deficit,
                         required_horizon_energy_kwh=required,
                         feasible_horizon_energy_kwh=required-deficit,
                         outside_horizon_assumed_energy_kwh=0.,
                         energy_feasibility_scope='individual charger bounds only; excludes shared capacity and safety curtailment',
                         paper_energy_constraints_feasible=deficit<=1e-8)
        return {s['id']:float(schedule[i,0]) for i,s in enumerate(sessions)}

    def _mpc(self,sim,sessions,profiles):
        from scipy.optimize import linprog
        from scipy.sparse import lil_matrix, vstack, csr_matrix
        n,h=len(sessions),len(profiles)
        # Variables: per-session/time kW, per-session battery-kWh deficit, peak kW.
        count=n*h+n+1
        bounds=[]
        required=[]
        for s in sessions:
            for t in range(h): bounds.append((0.,s['charger_kw'] if t<s['departure_step']-sim.index else 0.))
            required.append(s['remaining_kwh'])
        bounds += [(0.,required[i]) for i in range(n)]+[(0.,None)]
        rows=[]; rhs=[]
        for t,profile in enumerate(profiles):
            for weights,budget in capacity_constraints(sim,profile,sessions):
                rows.append({i*h+t:float(w) for i,w in enumerate(weights) if w}); rhs.append(budget)
            rows.append({**{i*h+t:1. for i in range(n)},count-1:-1.}); rhs.append(-sum(profile.values()))
        for i,s in enumerate(sessions):
            coefficient=sim.dt*s.get('efficiency',.9)
            rows.append({**{i*h+t:-coefficient for t in range(h)},n*h+i:-1.}); rhs.append(-required[i])
            rows.append({i*h+t:coefficient for t in range(h)}); rhs.append(s['remaining_kwh'])
        matrix=lil_matrix((len(rows),count))
        for r,values in enumerate(rows):
            for c,value in values.items(): matrix[r,c]=value
        matrix=matrix.tocsr()
        objective=np.zeros(count); objective[n*h:n*h+n]=1.
        first=linprog(objective,A_ub=matrix,b_ub=rhs,bounds=bounds,method='highs',options={'time_limit':self.options.solver_seconds})
        if not first.success:
            self.last.update(fallback='plain_least_laxity_first: delivery LP failed',solver_status=str(first.message))
            return {s['id']:s['charger_kw'] for s in sessions}
        deficit=float(first.fun)
        extra=csr_matrix(objective.reshape(1,-1))
        objective=np.zeros(count); objective[-1]=1.
        second=linprog(objective,A_ub=vstack([matrix,extra]),b_ub=[*rhs,deficit+1e-7],bounds=bounds,method='highs',options={'time_limit':self.options.solver_seconds})
        if not second.success:
            self.last.update(fallback='delivery-optimal schedule: peak LP failed',solver_status=str(second.message))
        else: self.last['solver_status']='optimal_for_linear_forecast_model'
        plan=second.x if second.success else first.x
        self.last['predicted_shortfall_kwh']=float(np.sum(plan[n*h:n*h+n]))
        return {s['id']:max(0.,float(plan[i*h])) for i,s in enumerate(sessions)}

    def observe(self,sim,interval):
        if self.name=='voltage_responsive':
            applied=sum(interval.get('applied_actions_kw',{}).values())
            raw=float(self.last.get('requested_kw',0.))
            self.last.update(raw_policy_kw=raw,applied_kw=applied,
                             safety_curtailed_kw=max(0.,raw-applied),
                             safety_intervened=raw-applied>1e-8,
                             safety_overlay='mandatory centralized capacity and AC shield')
        self.voltage_initialized=True
        interval['controller']=dict(self.last)
        self.voltages={b['id']:b.get('voltage_pu') for b in interval['blocks']} if interval['converged'] else {}
        self.voltages={key:value for key,value in self.voltages.items() if value is not None and math.isfinite(value)}
        # Last applied session power (rather than requested power) is recorded by the simulator when available.
        self.previous=dict(interval.get('applied_actions_kw',{}))


def create_controller(name,options=None):
    return ChargingController(name,options)
