"""Matched full-horizon validation and timing, separate from capacity claims."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mvgrid.novi_sad.playground.benchmark import BenchmarkService,session_pool,trial_summary
from mvgrid.novi_sad.playground.simulation import simulate_case
from mvgrid.novi_sad.playground.service import implementation_fingerprint,digest

service=BenchmarkService()
sid='suite-19f52a8c3215ac54a015'
fixture=service.get_suite(sid)
folder=ROOT/'artifacts/playground/aggregation-comparison'
folder.mkdir(parents=True,exist_ok=True)
report=dict(suite_id=sid,implementation=implementation_fingerprint(),conditions='Frozen node network and gross baseline, seed41001, 132 intervals. Each scenario prewarms loss reconciliation. Concurrent capacity benchmark may affect wall timings. CPU timings also recorded. No capacity maximum inferred.',pairs=[])
for scenario,count,strategies in [('normal',500,['immediate','capacity_aware','mpc']),('normal',4096,['immediate','capacity_aware','mpc']),('worst',4096,['immediate','capacity_aware'])]:
    sessions=session_pool(fixture['blocks'],41001,count)
    base=dict(seed=41001,network_path=str(service.path('benchmark-suites',sid)/'network.json'),blocks=fixture['blocks'],
              resolved_districts=fixture['districts'],limits=fixture['limits'],network_capacity=fixture['network_capacity'],
              demand_measurement='supply_including_losses',stop_on_violation=False)
    simulate_case(dict(base,strategy='immediate'),fixture['demand'][scenario],[])
    for strategy in strategies:
        runs=[]
        for aggregate in (False,True):
            wall=time.perf_counter();cpu=time.process_time()
            result=simulate_case(dict(base,strategy=strategy,aggregate_ev_nodes=aggregate),fixture['demand'][scenario],sessions)
            row=trial_summary(result)
            row.update(wall_seconds=time.perf_counter()-wall,cpu_seconds=time.process_time()-cpu,aggregate=aggregate,
                       fallback_intervals=sum(bool(i.get('controller',{}).get('fallback')) for i in result['intervals']),
                       demand_hash=digest(fixture['demand'][scenario]),sessions_hash=digest(sessions))
            row['node_traces']=[{b['id']:b['ev_kw'] for b in i['blocks']} for i in result['intervals']]
            runs.append(row)
            (folder/f'{scenario}-{count}-{strategy}-{aggregate}.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
            print(json.dumps(dict(scenario=scenario,cars=count,strategy=strategy,aggregate=aggregate,status=row['status'],wall=row['wall_seconds'])),flush=True)
        a,b=runs
        delta={k:b['metrics'][k]-a['metrics'][k] for k in ['delivered_energy_kwh','unmet_energy_kwh','peak_demand_kw','min_voltage_pu','max_line_loading_percent','max_transformer_loading_percent'] if a['metrics'].get(k) is not None and b['metrics'].get(k) is not None}
        pair=dict(scenario=scenario,cars=count,strategy=strategy,individual_status=a['status'],aggregated_status=b['status'],
                  individual_seconds=a['wall_seconds'],aggregated_seconds=b['wall_seconds'],speedup=a['wall_seconds']/b['wall_seconds'],
                  individual_cpu_seconds=a['cpu_seconds'],aggregated_cpu_seconds=b['cpu_seconds'],
                  individual_metrics=a['metrics'],aggregated_metrics=b['metrics'],metric_delta=delta,
                  individual_fallbacks=a['fallback_intervals'],aggregated_fallbacks=b['fallback_intervals'],
                  max_node_ev_difference_kw=max(abs(x[k]-y[k]) for x,y in zip(a['node_traces'],b['node_traces']) for k in x))
        report['pairs'].append(pair)
        (folder/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('COMPLETE',flush=True)
