"""Regenerate current alignment evidence with full-day and detailed snapshot checks."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.simulation import simulate_case
from mvgrid.novi_sad.playground.detailed import detailed_check
from mvgrid.novi_sad.playground.districts import resolve_districts
from mvgrid.novi_sad.playground.service import implementation_fingerprint


if __name__ == '__main__':
    net, blocks = build_network()
    started = time.perf_counter()
    baseline = simulate_case({'stop_on_violation': False}, [150000.] * 96, [])
    assert baseline['complete'] and baseline['metrics']['nonconverged_steps'] == 0
    comparison = detailed_check(baseline, [0])
    report = dict(
        inputs=dict(city_baseline_kw=150000, active_baseline_kw=150000,
                    ev_sessions=[], intervals=96, dt_hours=.25),
        excluded_sources=net['excluded_sources'],
        retained_demand_fraction=net['retained_demand_fraction'],
        network=dict(buses=len(net.bus), loads=len(net.load), lines=len(net.line),
                     transformers=len(net.trafo), sources=len(net.ext_grid)),
        capacity_alignment=net['capacity_alignment'],
        district_total_mw=sum(d['capacity_kw'] for d in resolve_districts(blocks))/1000,
        metrics=baseline['metrics'], comparison=comparison,
        validation_seconds=time.perf_counter()-started,
        fingerprint=implementation_fingerprint(),
        interpretation='User-estimate calibration, not independent validation. '
                       'Detailed snapshot uses the same delivery rating calibration. '
                       'Full-day check records all violations without relaxing limits.')
    target = REPOSITORY_ROOT / 'artifacts/playground/evidence/model_validation.json'
    target.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('network', 'district_total_mw', 'metrics')}, indent=2))
