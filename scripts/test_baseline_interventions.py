"""Explicit counterfactuals: voltage regulation and energy-preserving load shift.

These are proposed grid/demand interventions, never changes to default assumptions.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import copy
import json
import pandapower as pp
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.demand import generate_demand, allocate_block_demand
from mvgrid.novi_sad.playground.simulation import simulate_case
from mvgrid.novi_sad.playground.detailed import detailed_check


def shift_peak(day, cap):
    """Water-fill valleys after clipping peaks; maintain the exact daily energy."""
    if sum(day)>len(day)*cap:
        raise ValueError('Cap below mean demand cannot preserve energy')
    low,high=0.,cap
    for _ in range(70):
        level=(low+high)/2
        total=sum(min(cap,max(level,p)) for p in day)
        if total<sum(day): low=level
        else: high=level
    return [min(cap,max((low+high)/2,p)) for p in day]


def main():
    output=REPOSITORY_ROOT/'artifacts/playground/baseline-interventions'
    output.mkdir(parents=True,exist_ok=True)
    net,blocks=build_network()
    original=list(net.ext_grid.vm_pu)
    profile=generate_demand(dict(month=1,monthly_energy=120000,days_per_month=31,days=1,scenario='worst_case'))
    rows=[]
    for name,setpoint,cap,lvshare in [('unchanged',None,None,.5),('voltage_1.04',1.04,None,.5),
                                    ('lv_share_0.4',None,None,.4),('shift_200MW',None,200000,.5),
                                    ('voltage_1.04_and_shift_220MW',1.04,220000,.5)]:
        model=copy.deepcopy(net)
        if setpoint is not None: model.ext_grid.vm_pu=setpoint
        path=output/(name+'.json'); pp.to_json(model,str(path))
        day=shift_peak(profile,cap) if cap else profile
        demand=(day*2)[:132]
        allocation=allocate_block_demand(demand,blocks,{})
        result=simulate_case(dict(network_path=str(path),blocks=blocks,stop_on_violation=False,demand_measurement='supply_including_losses',
                                 network_capacity={'lv_baseline_fraction':lvshare,'lv_ev_fraction':1},
                                 block_demand_kw=allocation),demand,[])
        row=dict(name=name,source_setpoints_before=original,source_setpoints_after=list(model.ext_grid.vm_pu),
                 peak_cap_kw=cap,lv_baseline_fraction=lvshare,
                 daily_kwh_before=sum(profile)*.25,daily_kwh_after=sum(day)*.25,
                 shifted_kwh=sum(max(0,a-b) for a,b in zip(profile,day))*.25,
                 passed=result['complete'] and all(i['converged'] and not i['violations'] for i in result['intervals']),
                 metrics=result['metrics'],max_voltage_pu=max(i['max_voltage_pu'] for i in result['intervals']))
        rows.append(row)
        (output/'evidence.json').write_text(json.dumps(dict(case_origin='llm',
            scope='Engineering hypotheses, not available or measured grid controls. No defaults changed.',
            rows=rows),indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps(row),flush=True)


if __name__=='__main__': main()
