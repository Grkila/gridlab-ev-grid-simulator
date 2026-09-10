"""Isolated normal-winter voltage-support hypothesis; no default changes."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import json
import pandapower as pp
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.demand import generate_demand,allocate_block_demand
from mvgrid.novi_sad.playground.simulation import simulate_case


if __name__=='__main__':
    net,blocks=build_network()
    original=list(net.ext_grid.vm_pu)
    net.ext_grid.vm_pu=1.03
    folder=REPOSITORY_ROOT/'artifacts/playground/winter-voltage-hypothesis'
    folder.mkdir(parents=True,exist_ok=True)
    pp.to_json(net,str(folder/'network.json'))
    demand=generate_demand(dict(month=1,monthly_energy=120000,days_per_month=31,days=2))[:132]
    result=simulate_case(dict(network_path=str(folder/'network.json'),blocks=blocks,
        block_demand_kw=allocate_block_demand(demand,blocks,{}),demand_measurement='supply_including_losses',
        stop_on_violation=False),demand,[])
    evidence=dict(case_origin='llm',hypothesis='A 1% source-voltage setpoint increase resolves normal winter baseline undervoltage.',
        source_setpoints_before=original,source_setpoints_after=list(net.ext_grid.vm_pu),
        passed=result['complete'] and all(i['converged'] and not i['violations'] for i in result['intervals']),
        metrics=result['metrics'],max_voltage_pu=max(i['max_voltage_pu'] for i in result['intervals']),
        limitation='Synthetic sensitivity test; no evidence the real sources can or should use this setpoint. Demand, capacities and acceptance limits unchanged.')
    (folder/'evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence),flush=True)
