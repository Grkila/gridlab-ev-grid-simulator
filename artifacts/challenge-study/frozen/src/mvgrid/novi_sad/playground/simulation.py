"""Chronological 15-minute EV simulation with a fresh pandapower network per case."""
from __future__ import annotations
import copy
import math
import random
import time
import pandapower as pp
from pandapower.powerflow import LoadflowNotConverged
from .network import build_network
from .districts import district_id as get_district_id, resolve_districts
from .capacity_layers import capacity_layers, ev_stage_fraction
from .schema import NetworkCapacity
from .strategies import NEW_STRATEGIES, create_controller


class Simulator:
    """Small reset/step interface usable by future optimizer and RL adapters."""
    def reset(self, case, demand_kw, sessions, on_baseline_step=None):
        self.case = copy.deepcopy(case)
        self.net, self.blocks = (pp.from_json(case['network_path']),copy.deepcopy(case['blocks'])) if case.get('network_path') else build_network()
        self.by_id = {b['id']:b for b in self.blocks}
        self.resolved_districts=copy.deepcopy(case.get('resolved_districts')) if case.get('resolved_districts') is not None else resolve_districts(self.blocks,case.get('district_capacity'))
        self.district_by_id={d['id']:d for d in self.resolved_districts}
        for b in self.blocks:
            if get_district_id(b) not in self.district_by_id: raise ValueError('Frozen districts do not cover network blocks')
        self.demand = list(demand_kw)
        self.dt = float(case.get('dt_hours',.25))
        if not math.isfinite(self.dt) or self.dt <= 0: raise ValueError('dt_hours must be finite and positive')
        if any(not math.isfinite(v) or v < 0 for v in self.demand): raise ValueError('Demand must be finite and nonnegative')
        self.loss_reconciliation=[]
        self.input_demand=list(self.demand)
        if case.get('demand_measurement','load')=='supply_including_losses':
            from .loss_accounting import reconcile_supply
            allocation=self.case.get('block_demand_kw') or {b['id']:[p*b['base_weight'] for p in self.demand] for b in self.blocks}
            allocation,self.loss_reconciliation=reconcile_supply(self.net,self.blocks,allocation,on_baseline_step)
            self.case['block_demand_kw']=allocation
            self.demand=[sum(values[t] for values in allocation.values()) for t in range(len(self.demand))]
        self.sessions = copy.deepcopy(sessions)
        rng = random.Random(case.get('seed',0))
        ids = set()
        for s in sorted(self.sessions,key=lambda x:str(x['id'])):
            if s['id'] in ids: raise ValueError('Duplicate session ID')
            ids.add(s['id'])
            if s['block_id'] not in self.by_id: raise ValueError('Unknown session block')
            s['district_id']=get_district_id(self.by_id[s['block_id']])
            for field in ('arrival_step','departure_step'):
                value=s[field]
                if isinstance(value,bool) or not math.isfinite(value) or int(value)!=value:
                    raise ValueError('Session window indices must be finite integers')
                s[field]=int(value)
            if not (0 <= s['arrival_step'] < s['departure_step']): raise ValueError('Invalid session window')
            if not all(math.isfinite(value) for value in (s['energy_kwh'],s['charger_kw'],s.get('efficiency',.9))):
                raise ValueError('Energy, charger and efficiency must be finite')
            if s['energy_kwh'] < 0 or s['charger_kw'] <= 0 or not 0 < s.get('efficiency',.9) <= 1: raise ValueError('Invalid energy, charger or efficiency')
            s['remaining_kwh'] = float(s['energy_kwh'])
            s['delivered_kwh'] = 0.
            s['delay_jitter'] = rng.randrange(max(1,int(4/self.dt)))
        self.stopped = False
        self.vehicle_count = len(self.sessions)
        if case.get('aggregate_ev_nodes'):
            if case.get('strategy') == 'rl':
                raise ValueError('Node aggregation requires continuous charging, not a per-car binary RL policy.')
            from .node_aggregation import aggregate_sessions
            self.sessions = aggregate_sessions(self.sessions, case.get('strategy') == 'randomized_delay')
        self.index = 0
        self.intervals = []
        self.daily_energy_kwh = 0.
        self.energy_day = None
        return self.observation()

    def observation(self):
        return {'step':self.index,'baseline_kw':self.demand[self.index] if self.index<len(self.demand) else None,'sessions':[{k:v for k,v in s.items() if k!='delay_jitter'} for s in self.sessions if s['arrival_step']<=self.index<s['departure_step']],'done':self.stopped or self.index>=len(self.demand)}

    def measure_baseline_voltages(self):
        """Measure current modeled baseline without advancing time or EV energy."""
        if self.index>=len(self.demand):
            return {}
        measured=copy.deepcopy(self.net)
        for block in self.blocks:
            kw=(float(self.case['block_demand_kw'][block['id']][self.index])
                if self.case.get('block_demand_kw') else self.demand[self.index]*block['base_weight'])
            p=kw/1000
            measured.load.loc[block['load_index'],['p_mw','q_mvar']]=[p,p*math.tan(math.acos(.97))]
        try:
            pp.runpp(measured,numba=False,init='auto',max_iteration=int(self.case.get('max_iteration',30)))
        except LoadflowNotConverged:
            return {}
        return {b['id']:float(measured.res_bus.at[b['bus_index'],'vm_pu']) for b in self.blocks
                if math.isfinite(float(measured.res_bus.at[b['bus_index'],'vm_pu']))}

    def step_node_loads(self, node_power_kw):
        """Apply one EV kW target per node; allocate by departure internally.

        Unspecified nodes are off. Targets are capped by connected chargers and
        remaining energy; ordinary grid checks still evaluate the resulting load.
        """
        if not self.case.get('aggregate_ev_nodes'):
            raise ValueError('Node power commands require aggregate_ev_nodes.')
        budgets = {}
        for node, power in node_power_kw.items():
            if node not in self.by_id or not math.isfinite(power) or power < 0:
                raise ValueError('Invalid node charging target')
            budgets[node] = float(power)
        actions = {}
        for s in sorted(self.sessions,key=lambda s:(s['departure_step'],str(s['id']))):
            if not s['arrival_step'] <= self.index < s['departure_step']: continue
            node=s['block_id']
            power=min(budgets.get(node,0.),s['charger_kw'],s['remaining_kwh']/(self.dt*s.get('efficiency',.9)))
            actions[s['id']]=power
            budgets[node]=max(0.,budgets.get(node,0.)-power)
        result=self.step(actions)
        result[1]['node_power_targets_kw']=dict(node_power_kw)
        return result

    def step(self, charging_actions=None):
        if self.stopped or self.index >= len(self.demand): raise RuntimeError('Simulation finished')
        t = self.index
        baseline = {b['id']:float(self.case['block_demand_kw'][b['id']][t]) if self.case.get('block_demand_kw') else self.demand[t]*b['base_weight'] for b in self.blocks}
        loading_factor = self.case.get('limits',{}).get('max_loading_percent',100)/100
        strategy = self.case.get('strategy','immediate')
        if strategy not in ('immediate','fixed_delay','randomized_delay','capacity_aware','rl',*NEW_STRATEGIES): raise ValueError('Unknown strategy')
        if strategy in ('rl',*NEW_STRATEGIES) and charging_actions is None: raise ValueError(f'{strategy} strategy requires a loaded controller')
        connected = [s for s in self.sessions if s['arrival_step']<=t<s['departure_step']]
        source_remaining = {}
        block_remaining = {}
        district_remaining={d['id']:d['capacity_kw'] for d in self.resolved_districts}
        stage_remaining={r['id']:r['headroom_kw'] for r in capacity_layers(self.net, self.blocks, baseline, {b['id']:0. for b in self.blocks}, self.case.get('network_capacity'))}
        for b in self.blocks:
            source_remaining.setdefault(b['source_id'],b['source_capacity_kw']*loading_factor)
            source_remaining[b['source_id']] -= baseline[b['id']]
            block_remaining[b['id']] = max(0,b['capacity_kw']*loading_factor-baseline[b['id']])
            district_remaining[get_district_id(b)]-=baseline[b['id']]
        allocations = {}
        requested_power = {}
        for s in sorted(connected,key=lambda x:(x['departure_step'],str(x['id']))):
            power = min(s['charger_kw'],s['remaining_kwh']/(self.dt*s.get('efficiency',.9)))
            if charging_actions is not None:
                requested = float(charging_actions.get(s['id'],0))
                if not math.isfinite(requested) or requested<0: raise ValueError('Invalid charging action')
                power = min(power,requested)
            elif strategy in ('fixed_delay','randomized_delay'):
                day_steps = int(round(24/self.dt))
                start = (s['arrival_step']//day_steps)*day_steps + int(self.case.get('fixed_start_hour',23)/self.dt)
                # Arrivals after scheduled start charge immediately; early arrivals wait.
                if strategy == 'randomized_delay': start += s['delay_jitter']
                if t<max(s['arrival_step'],start): power = 0.
            requested_power[s['id']] = power
            if strategy in ('capacity_aware','voltage_responsive'):
                b = self.by_id[s['block_id']]
                power = min(power,block_remaining[b['id']],max(0,source_remaining[b['source_id']]),max(0,district_remaining[get_district_id(b)]))
                for stage, remaining in stage_remaining.items():
                    share=ev_stage_fraction(stage,b,self.case.get('network_capacity'))
                    if share: power=min(power,max(0,remaining)/share)
                for stage in stage_remaining:
                    stage_remaining[stage]-=power*ev_stage_fraction(stage,b,self.case.get('network_capacity'))
                block_remaining[b['id']] -= power
                source_remaining[b['source_id']] -= power
                district_remaining[get_district_id(b)]-=power
            allocations[s['id']] = max(0,power)
        ev = {b['id']:0. for b in self.blocks}
        for s in connected: ev[s['block_id']] += allocations[s['id']]
        for b in self.blocks:
            p = (baseline[b['id']]+ev[b['id']])/1000
            self.net.load.loc[b['load_index'],['p_mw','q_mvar']] = [p,p*math.tan(math.acos(.97))]
        converged = True
        try:
            pp.runpp(self.net,numba=False,init='results' if t and self.net.converged else 'auto',max_iteration=int(self.case.get('max_iteration',30)))
        except LoadflowNotConverged:
            converged = False
        limits = {'min_voltage_pu':.95,'max_voltage_pu':1.05,'max_loading_percent':100,**self.case.get('limits',{})}
        safety_iterations = 0
        def stage_states():
            rows=capacity_layers(self.net,self.blocks,baseline,ev,self.case.get('network_capacity'),
                float(self.net.res_ext_grid.p_mw.sum())*1000 if converged else None)
            if not converged:
                for row in rows:
                    if row['id']=='transmission':
                        row.update(demand_kw=None,headroom_kw=None,installed_headroom_kw=None,loading_percent=None,installed_loading_percent=None,reserve_used_kw=None,reserve_remaining_kw=None,capacity_exceeded=False)
            return rows
        def electrically_safe():
            return converged and self.net.res_bus.vm_pu.min() >= limits['min_voltage_pu'] and self.net.res_bus.vm_pu.max() <= limits['max_voltage_pu'] and self.net.res_line.loading_percent.max() <= limits['max_loading_percent'] and self.net.res_trafo.loading_percent.max() <= limits['max_loading_percent'] and not any(r['capacity_exceeded'] for r in stage_states())
        if strategy == 'capacity_aware' or strategy in NEW_STRATEGIES or (strategy == 'rl' and (self.case.get('rl') or {}).get('safety_shield',True)):
            # Bounded conservative AC safety wrapper. Last attempt removes all EV power;
            # residual violations then belong to the baseline, never hidden by clipping.
            while not electrically_safe() and sum(allocations.values()) > 1e-9 and safety_iterations < 8:
                safety_iterations += 1
                factor = 0. if safety_iterations == 8 else .5
                if strategy == 'rl':
                    # Preserve binary commands: remove complete charger allocations,
                    # keeping the nearest departures, rather than halve their power.
                    active = [s['id'] for s in sorted(connected,key=lambda s:(s['departure_step'],str(s['id']))) if allocations[s['id']]>1e-9]
                    keep = set(active[:len(active)//2]) if factor else set()
                    allocations = {key:value if key in keep else 0. for key,value in allocations.items()}
                else:
                    allocations = {key:value*factor for key,value in allocations.items()}
                ev = {b['id']:0. for b in self.blocks}
                for session in connected: ev[session['block_id']] += allocations[session['id']]
                for block in self.blocks:
                    p = (baseline[block['id']]+ev[block['id']])/1000
                    self.net.load.loc[block['load_index'],['p_mw','q_mvar']] = [p,p*math.tan(math.acos(.97))]
                try:
                    pp.runpp(self.net,numba=False,init='auto',max_iteration=int(self.case.get('max_iteration',30)))
                    converged = True
                except LoadflowNotConverged:
                    converged = False
        violations = []
        snapshots = []
        # EV energy is requested consumption even if a steady-state solution fails; no protection model is implied.
        for s in connected:
            delivered = allocations[s['id']]*self.dt*s.get('efficiency',.9)
            s['remaining_kwh'] = max(0,s['remaining_kwh']-delivered)
            s['delivered_kwh'] += delivered
        for b in self.blocks:
            voltage = float(self.net.res_bus.at[b['bus_index'],'vm_pu']) if converged else None
            line_indices = list(dict.fromkeys([b['line_index'], *b.get('upstream_line_indices',[])]))
            trafo_indices = list(dict.fromkeys([b['trafo_index'], *b.get('upstream_trafo_indices',[])]))
            line = max(float(self.net.res_line.at[i,'loading_percent']) for i in line_indices) if converged else None
            trafo = max(float(self.net.res_trafo.at[i,'loading_percent']) for i in trafo_indices) if converged else None
            vehicles=[]
            counts=dict(connected=0,charging=0,waiting=0,completed=0,departed_shortfall=sum(s.get('vehicle_count',1) for s in self.sessions if s['block_id']==b['id'] and s['departure_step']<=t+1 and s['remaining_kwh']>1e-6))
            for s in connected:
                if s['block_id']!=b['id']: continue
                status = 'charging' if allocations[s['id']]>1e-9 else 'completed' if s['remaining_kwh']<=1e-6 else 'waiting'
                counts['connected']+=s.get('vehicle_count',1)
                counts[status]+=s.get('vehicle_count',1)
                vehicles.append(dict(id=s['id'],vehicle_count=s.get('vehicle_count',1),district_id=s['district_id'],status=status,power_kw=allocations[s['id']],remaining_kwh=s['remaining_kwh']))
            snapshots.append(dict(id=b['id'],baseline_kw=baseline[b['id']],ev_kw=ev[b['id']],total_kw=baseline[b['id']]+ev[b['id']],voltage_pu=voltage,line_loading_percent=line,transformer_loading_percent=trafo,counts=counts,vehicles=vehicles))
        # Check every retained electrical asset, including upstream delivery chains.
        def affected(kind,index):
            if kind=='bus':
                return [b for b in self.blocks if index in [b['bus_index'], *b.get('upstream_bus_indices',b.get('path_bus_indices',[]))]]
            own='line_index' if kind=='line' else 'trafo_index'
            chain='upstream_line_indices' if kind=='line' else 'upstream_trafo_indices'
            return [b for b in self.blocks if index in [b[own], *b.get(chain,[])]]
        if converged:
            for asset_type, table, values, field in [('bus',self.net.bus,self.net.res_bus,'vm_pu'),('line',self.net.line,self.net.res_line,'loading_percent'),('transformer',self.net.trafo,self.net.res_trafo,'loading_percent')]:
                for index,row in table.iterrows():
                    value=float(values.at[index,field])
                    candidates=[('undervoltage',limits['min_voltage_pu'],value<limits['min_voltage_pu']),('overvoltage',limits['max_voltage_pu'],value>limits['max_voltage_pu'])] if asset_type=='bus' else [(asset_type+'_overload',limits['max_loading_percent'],value>limits['max_loading_percent'])]
                    for kind,limit,bad in candidates:
                        if not bad: continue
                        downstream=affected(asset_type,index)
                        for block in downstream or [None]:
                            violations.append(dict(kind=kind,asset_id=str(row['name']),asset_type=asset_type,asset_index=int(index),block_id=block['id'] if block else None,value=value,limit=limit))
        else:
            violations.append(dict(kind='nonconvergence',asset_id='network',value=None,limit=None))
        stages=stage_states()
        for row in stages:
            if row['capacity_exceeded']:
                violations.append(dict(kind='network_capacity_exceeded',asset_type='capacity_stage',asset_id=row['id'],value=row['demand_kw'],limit=row['capacity_kw'],block_ids=row['block_ids']))
        transformers=[]
        for index,row in self.net.trafo.iterrows():
            downstream=affected('transformer',index)
            transformers.append(dict(id=str(row['name']),index=int(index),hv_kv=float(row.vn_hv_kv),lv_kv=float(row.vn_lv_kv),rating_mva=float(row.sn_mva),
                p_mw=float(self.net.res_trafo.at[index,'p_hv_mw']) if converged else None,
                q_mvar=float(self.net.res_trafo.at[index,'q_hv_mvar']) if converged else None,
                loading_percent=float(self.net.res_trafo.at[index,'loading_percent']) if converged else None,
                block_ids=[b['id'] for b in downstream],district_ids=sorted({b.get('delivery_station_id',b.get('delivery_id',b['source_id'])) for b in downstream}),
                has_violation=not converged or any(v.get('asset_type')=='transformer' and v.get('asset_index')==index for v in violations)))
        districts={}
        for block in self.blocks:
            district_id=get_district_id(block)
            district=districts.setdefault(district_id,dict(**self.district_by_id[district_id],baseline_kw=0.,ev_kw=0.,total_kw=0.,has_violation=False,counts=dict(connected=0,charging=0,waiting=0,completed=0,departed_shortfall=0)))
            district['baseline_kw']+=baseline[block['id']]
            district['ev_kw']+=ev[block['id']]
            district['total_kw']+=baseline[block['id']]+ev[block['id']]
            district['has_violation'] |= not converged or any(v.get('block_id')==block['id'] for v in violations)
        for district in districts.values():
            district['headroom_kw']=district['capacity_kw']-district['total_kw']
            district['loading_percent']=district['total_kw']/district['capacity_kw']*100
            exceeded=district['total_kw']>district['capacity_kw']+1e-9
            district['capacity_exceeded']=exceeded
            district['has_violation'] |= exceeded
            if exceeded:
                violations.append(dict(kind='district_capacity_exceeded',asset_type='district',asset_id=district['id'],district_id=district['id'],value=district['total_kw'],limit=district['capacity_kw'],block_ids=district['block_ids']))
            for snapshot in snapshots:
                if snapshot['id'] not in district['block_ids']: continue
                snapshot.update(district_id=district['id'],district_loading_percent=district['loading_percent'],district_capacity_exceeded=exceeded)
                for key,value in snapshot['counts'].items(): district['counts'][key]+=value
        interval=dict(step=t,safety_iterations=safety_iterations,baseline_kw=sum(baseline.values()),requested_ev_kw=sum(requested_power.values()),curtailed_ev_kw=max(0,sum(requested_power.values())-sum(ev.values())),ev_kw=sum(ev.values()),total_kw=sum(baseline.values())+sum(ev.values()),converged=converged,min_voltage_pu=float(self.net.res_bus.vm_pu.min()) if converged else None,max_line_loading_percent=float(self.net.res_line.loading_percent.max()) if converged else None,max_transformer_loading_percent=float(self.net.res_trafo.loading_percent.max()) if converged else None,losses_kw=float((self.net.res_line.pl_mw.sum()+self.net.res_trafo.pl_mw.sum())*1000) if converged else None,violations=violations,blocks=snapshots,transformers=transformers,districts=list(districts.values()))
        day = int(t*self.dt//24)
        if self.energy_day != day: self.energy_day = day; self.daily_energy_kwh = 0.
        energy_before = self.daily_energy_kwh
        self.daily_energy_kwh += interval['total_kw']*self.dt
        energy_limit = (self.case.get('rl') or {}).get('daily_energy_limit_kwh')
        interval.update(daily_energy_kwh=self.daily_energy_kwh,energy_excess_kwh=0.,energy_limit_exceeded=False)
        if energy_limit:
            interval['energy_excess_kwh'] = max(0.,self.daily_energy_kwh-energy_limit)-max(0.,energy_before-energy_limit)
            interval['energy_limit_exceeded'] = self.daily_energy_kwh>energy_limit+1e-9
            if interval['energy_limit_exceeded']:
                violations.append(dict(kind='daily_energy_exceeded',asset_type='energy_budget',asset_id='city_load',value=self.daily_energy_kwh,limit=energy_limit))
        self.intervals.append(interval)
        interval['applied_actions_kw'] = dict(allocations)
        interval['capacity_layers']=stages
        interval['supply_kw']=float(self.net.res_ext_grid.p_mw.sum())*1000 if converged else None
        interval['max_voltage_pu']=float(self.net.res_bus.vm_pu.max()) if converged else None
        if self.loss_reconciliation:
            interval['baseline_reconciliation']=self.loss_reconciliation[t]
            interval['incremental_ev_supply_kw']=interval['supply_kw']-self.loss_reconciliation[t]['resolved_supply_kw'] if converged else None
        interval['max_network_capacity_loading_percent']=max((r['loading_percent'] for r in stages if r['loading_percent'] is not None),default=None)
        interval['max_district_loading_percent']=max(d['loading_percent'] for d in districts.values())
        self.index += 1
        self.stopped = bool(self.case.get('stop_on_violation',True) and violations)
        return self.observation(),interval,self.stopped or self.index>=len(self.demand)


def simulate_case(case, demand_kw, sessions, on_step=None, controller=None):
    started=time.perf_counter()
    simulator=Simulator()
    simulator.reset(case,demand_kw,sessions,on_step)
    if case.get('strategy') in NEW_STRATEGIES and controller is None:
        controller = create_controller(case['strategy'],case.get('strategy_options'))
    if case.get('strategy') == 'rl' and controller is None:
        from .rl import BinaryPolicy, RLController
        if not case.get('rl_policy'): raise ValueError('Frozen RL policy is missing')
        controller = RLController(BinaryPolicy.from_dict(case['rl_policy']),case.get('rl'))
    while simulator.index<len(simulator.demand) and not simulator.stopped:
        _,interval,_=simulator.step(controller.actions(simulator) if controller else None)
        if controller: controller.observe(simulator,interval)
        if on_step: on_step(interval)
    intervals=simulator.intervals
    def maximum(key): return max((i[key] for i in intervals if i[key] is not None),default=None)
    metrics=dict(peak_demand_kw=maximum('total_kw'),max_line_loading_percent=maximum('max_line_loading_percent'),max_transformer_loading_percent=maximum('max_transformer_loading_percent'),min_voltage_pu=min((i['min_voltage_pu'] for i in intervals if i['min_voltage_pu'] is not None),default=None),nonconverged_steps=sum(not i['converged'] for i in intervals),overload_steps=sum(any(v['kind'] in ('line_overload','transformer_overload') for v in i['violations']) for i in intervals),voltage_violation_steps=sum(any(v['kind'] in ('undervoltage','overvoltage') for v in i['violations']) for i in intervals),unmet_energy_kwh=sum(s['remaining_kwh'] for s in simulator.sessions if s['departure_step']<=len(intervals)),pending_energy_kwh=sum(s['remaining_kwh'] for s in simulator.sessions if s['departure_step']>len(intervals)),requested_energy_kwh=sum(s['energy_kwh'] for s in simulator.sessions),delivered_energy_kwh=sum(s['delivered_kwh'] for s in simulator.sessions),grid_ev_energy_kwh=sum(i['ev_kw']*simulator.dt for i in intervals),runtime_seconds=time.perf_counter()-started)
    metrics.update(vehicle_count=simulator.vehicle_count,controlled_cohorts=len(simulator.sessions),aggregate_ev_nodes=bool(case.get('aggregate_ev_nodes')),
                   max_district_loading_percent=maximum('max_district_loading_percent'),district_overload_steps=sum(any(v['kind']=='district_capacity_exceeded' for v in i['violations']) for i in intervals))
    metrics.update(max_network_capacity_loading_percent=maximum('max_network_capacity_loading_percent'),network_capacity_overload_steps=sum(any(v['kind']=='network_capacity_exceeded' for v in i['violations']) for i in intervals) if any(i.get('capacity_layers') for i in intervals) else None)
    metrics.update(energy_excess_kwh=sum(i.get('energy_excess_kwh',0.) for i in intervals),energy_limit_exceeded_steps=sum(i.get('energy_limit_exceeded',False) for i in intervals))
    metrics.update(supply_peak_kw=maximum('supply_kw'),load_peak_kw=maximum('total_kw'),
                   network_losses_kwh=sum(i['losses_kw']*simulator.dt for i in intervals if i['losses_kw'] is not None))
    if simulator.loss_reconciliation:
        metrics.update(peak_demand_kw=maximum('supply_kw'),
            baseline_input_energy_kwh=sum(r['input_supply_kw']*simulator.dt for r in simulator.loss_reconciliation[:len(intervals)]),
            baseline_loss_reconciliation_max_error_kw=max(abs(r['error_kw']) for r in simulator.loss_reconciliation),
            incremental_ev_supply_energy_kwh=sum(i['incremental_ev_supply_kw']*simulator.dt for i in intervals if i['incremental_ev_supply_kw'] is not None))
    if case.get('strategy') == 'rl':
        metrics.update(rl_reward=sum(i['rl']['reward'] for i in intervals),rl_switches=sum(i['rl']['switches'] for i in intervals),
                       rl_interventions=sum(i['rl']['interventions'] for i in intervals),energy_excess_kwh=sum(i['rl']['energy_excess_kwh'] for i in intervals))
    return dict(operating_scenario=simulator.net.get("operating_scenario"),demand_measurement=simulator.case.get("demand_measurement","load"),excluded_hubs=simulator.net.get("excluded_hubs",[]),network_capacity=NetworkCapacity.model_validate(simulator.case.get("network_capacity",{})).model_dump(),capacity_alignment=simulator.net.get("capacity_alignment"),metrics=metrics,intervals=intervals,blocks=simulator.blocks,sessions=simulator.sessions,resolved_districts=simulator.resolved_districts,hierarchy_nodes=simulator.net.get("hierarchy_nodes",[]),hierarchy_edges=simulator.net.get("hierarchy_edges",[]),excluded_sources=simulator.net.get("excluded_sources",[]),complete=not simulator.stopped and simulator.index==len(simulator.demand),stop_reason={'step':intervals[-1]['step'],'violations':intervals[-1]['violations']} if simulator.stopped else None)
