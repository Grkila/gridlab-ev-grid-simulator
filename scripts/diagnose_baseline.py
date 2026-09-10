"""Reproducible model-reduction hypotheses; never alters the active network."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import copy
import hashlib
import json
import math
import time
from collections import defaultdict
import networkx as nx
import pandapower as pp
from mvgrid.paths import REPOSITORY_ROOT, NOVI_SAD_MODEL_DIR
from mvgrid.novi_sad.playground.network import build_network, REDUCED_PATH
from mvgrid.novi_sad.playground.rebalance import rebalance_sources
from mvgrid.novi_sad.playground.demand import generate_demand, allocate_block_demand
from mvgrid.novi_sad.playground.simulation import simulate_case
from mvgrid.novi_sad.playground.detailed import detailed_check


def main():
    output = REPOSITORY_ROOT / 'artifacts/playground/baseline-diagnosis'
    output.mkdir(parents=True, exist_ok=True)
    net, blocks = build_network()
    full = pp.from_json(str(NOVI_SAD_MODEL_DIR / 'ppnet_novi_sad.json'))
    rebalance_sources(full, net['excluded_sources'])
    graph = nx.Graph()
    for i, row in full.line.iterrows():
        graph.add_edge(int(row.from_bus), int(row.to_bus), index=int(i))
    loads = {str(row.synthetic_id): (int(row.bus), float(row.p_mw)) for _, row in full.load.iterrows()}
    q_ratio = math.tan(math.acos(.97))
    candidates = {name: copy.deepcopy(net) for name in ('loss_weighted', 'worst_path')}
    corrections = []
    for block in blocks:
        if not block['member_ids']: continue
        root = int(full.trafo.loc[full.trafo.station_id == block['delivery_id'], 'lv_bus'].iloc[0])
        paths = {m: nx.shortest_path(graph, root, loads[m][0]) for m in block['member_ids']}
        edge_power = defaultdict(float)
        member_edges = {}
        total = sum(loads[m][1] for m in paths)
        for member, path in paths.items():
            member_edges[member] = [graph[a][b]['index'] for a,b in zip(path,path[1:])]
            for e in member_edges[member]: edge_power[e] += loads[member][1]
        impedance = {e: complex(float(full.line.at[e,'r_ohm_per_km']), float(full.line.at[e,'x_ohm_per_km']))
                      * float(full.line.at[e,'length_km']) / int(full.line.at[e,'parallel']) for e in edge_power}
        loss_z = sum(impedance[e] * (p/total)**2 for e,p in edge_power.items())
        voltage_z = {m: sum(impedance[e]*edge_power[e]/total for e in edges) for m,edges in member_edges.items()}
        worst_member = max(voltage_z, key=lambda m: voltage_z[m].real + q_ratio*voltage_z[m].imag)
        worst_z = voltage_z[worst_member]
        line = block['line_index']
        corrections.append(dict(block=block['id'], old_r=float(net.line.at[line,'r_ohm_per_km']),
                                loss_r=loss_z.real, worst_r=worst_z.real, worst_member=worst_member))
        for name,z in [('loss_weighted',loss_z),('worst_path',worst_z)]:
            candidates[name].line.loc[line,['r_ohm_per_km','x_ohm_per_km']] = [max(.001,z.real),max(.001,z.imag)]
    networks = {'original': net, **candidates}
    paths = {}
    for name, model in networks.items():
        paths[name] = output / (name+'.json')
        pp.to_json(model, str(paths[name]))
    evidence = dict(original_network_sha256=hashlib.sha256(REDUCED_PATH.read_bytes()).hexdigest(),
                    hypotheses=['H1 demand/units error', 'H2 reduction exaggerates branch voltage drop',
                                'H3 assumed downstream share already exceeds LV capacity'],
                    corrections=corrections, cases=[])
    for name,month,energy,days,worst in [('normal',6,76000,30,False),('winter',1,120000,31,False),
                                      ('worst_winter',1,120000,31,True),('worst_summer',6,76000,30,True)]:
        demand = generate_demand(dict(month=month,monthly_energy=energy,days_per_month=days,days=2,
                                     scenario='worst_case' if worst else 'base'))[:132]
        allocation = allocate_block_demand(demand, blocks, {})
        row = dict(scenario=name, daily_kwh=sum(demand[:96])*.25,
                   expected_daily_kwh=energy*1000/days*(1.2 if worst else 1),
                   allocation_max_error_kw=max(abs(sum(v[t] for v in allocation.values())-p) for t,p in enumerate(demand)),
                   peak_kw=max(demand), lv_share_threshold=120000/max(demand), models={})
        for model,path in paths.items():
            result = simulate_case(dict(network_path=str(path),blocks=blocks,stop_on_violation=False,
                                        block_demand_kw=allocation), demand, [])
            peak = max(range(len(demand)), key=demand.__getitem__)
            worst_step = min(range(len(result['intervals'])),key=lambda t: result['intervals'][t]['min_voltage_pu'])
            row['models'][model] = dict(metrics=result['metrics'], worst_step=worst_step,
                                       peak_step=peak, complete=result['complete'])
            if model == 'original':
                row['detailed'] = detailed_check(result, sorted({peak,worst_step}))
        evidence['cases'].append(row)
        (output/'evidence.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps(row),flush=True)


if __name__ == '__main__':
    main()
