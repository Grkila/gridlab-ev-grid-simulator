"""Independent read-only evidence audit; writes only its own review result.

Use --require-complete for the final gate and --ac for independent AC spot checks.
This deliberately does not import the study runner or its static-state evaluator.
"""
from pathlib import Path
import argparse
import calendar
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'challenge-study-v2'
FROZEN = OUT / 'frozen'
PHOTO = {
    '2024': [113883,105207,100219,88797,76792,74739,78034,76745,82901,95688,106247,120553],
    '2025': [116985,108060,102944,91743,79361,76965,80282,78409,84928,98283,109459,124221],
}

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def independent_ac(fixture, hour, weights, power):
    """Rebuild electrical state without any challenge evaluator/controller code."""
    import pandapower as pp
    import numpy as np
    net = pp.from_json(str(FROZEN / (fixture['mode'] + '.json')))
    blocks = read(FROZEN / 'blocks.json')
    step = round(hour * 4)
    baseline = {b['id']: fixture['allocation'][b['id']][step] for b in blocks}
    ev = {b['id']: power * weights.get(b['id'], 0.) for b in blocks}
    for b in blocks:
        mw = (baseline[b['id']] + ev[b['id']]) / 1000
        net.load.loc[b['load_index'], ['p_mw', 'q_mvar']] = [mw, mw * math.tan(math.acos(.97))]
    try:
        pp.runpp(net, numba=False, init='flat', max_iteration=60)
    except pp.LoadflowNotConverged:
        return {'status': 'unknown'}
    values = [net.res_bus.vm_pu.min(), net.res_bus.vm_pu.max(), net.res_line.loading_percent.max(), net.res_trafo.loading_percent.max(), net.res_ext_grid.p_mw.sum()*1000]
    if not np.isfinite(values).all():
        return {'status': 'unknown'}
    reasons = []
    if values[0] < .95 or values[1] > 1.05: reasons.append('voltage')
    if values[2] > 100 or values[3] > 100: reasons.append('thermal')
    estimate = net['capacity_alignment']['estimate']
    fraction = float(net.get('retained_demand_fraction', 1.))
    total_lv = sum(baseline.values()) * .5 + sum(ev.values())
    if values[4] > estimate['transmission_mw'] * fraction * 1000 + 1e-6: reasons.append('transmission')
    if total_lv > estimate['transformer_mw'] * fraction * 1000 + 1e-6: reasons.append('lv_transformers')
    if total_lv > estimate['distribution_by_voltage_mw']['0.4'] * fraction * 1000 + 1e-6: reasons.append('lv_network')
    for voltage in (10, 20):
        members = [b for b in blocks if b['delivery_voltage_kv'] == voltage]
        rating = sum({b['delivery_id']: b['delivery_capacity_kw'] for b in members}.values())
        if sum(baseline[b['id']] + ev[b['id']] for b in members) > rating + 1e-6: reasons.append('mv_delivery')
    for d in read(FROZEN / 'districts.json'):
        if sum(baseline[b] + ev[b] for b in d['block_ids']) > d['capacity_kw'] + 1e-6: reasons.append('district')
    return {'status': 'failed' if reasons else 'passed', 'min_voltage_pu': float(values[0]), 'supply_kw': float(values[4]), 'reasons': reasons}

def audit(require_complete=False, ac=False):
    errors, pending, warnings, spot_checks = [], [], [], []
    def check(condition, message):
        if not condition: errors.append(message)
    manifest = read(FROZEN / 'manifest.json')
    for name, expected in manifest['source_hashes'].items():
        path = FROZEN / name
        check(path.exists() and sha(path) == expected, 'Frozen file changed: ' + name)
    check(manifest['monthly_mwh'] == PHOTO, 'Manifest monthly transcription differs from independently read photo')
    runner_hash = sha(ROOT / 'scripts' / 'challenge_study.py')
    fixtures = {}
    for path in (OUT / 'fixtures').glob('*.json'):
        f = read(path); fixtures[f['id']] = f
        payload = {k:v for k,v in f.items() if k != 'hash'}
        check(digest(payload) == f['hash'], 'Fixture digest: ' + f['id'])
        expected = PHOTO[str(f['year'])][f['month']-1] * 1000 / calendar.monthrange(f['year'],f['month'])[1] * f['stress']
        check(abs(expected-f['daily_kwh']) < 1e-5, 'Fixture daily energy: ' + f['id'])
        check(len(f['gross_kw']) == len(f['net_kw']) == 132, 'Fixture horizon: ' + f['id'])
        check(all(abs(sum(v[t] for v in f['allocation'].values())-f['net_kw'][t])<1e-6 for t in range(132)), 'Fixture node allocation: '+f['id'])
        check(max(abs(x['error_kw']) for x in f['reconciliation']) <= .010001, 'Loss reconciliation: '+f['id'])
    runs = {p.stem: read(p) for p in (OUT/'runs').glob('*.json')}
    current = {k:r for k,r in runs.items() if r['parameters'].get('runner_hash') == runner_hash}
    paired = {}
    for rid, r in current.items():
        p, m = r['parameters'], r['metrics']
        snap = FROZEN/'runners'/(p['runner_hash']+'.py')
        check(snap.exists() and sha(snap)==p['runner_hash'], 'Runner snapshot: '+rid)
        check(digest(p)[:20] == rid == r['id'], 'Run parameter digest: '+rid)
        check(p['fixture'] in fixtures and p['fixture_hash']==fixtures[p['fixture']]['hash'], 'Run fixture binding: '+rid)
        check(len(r['trace'])==132 and [i['step'] for i in r['trace']]==list(range(132)) and r['complete'], 'Incomplete run: '+rid)
        check(all(math.isfinite(m[k]) and m[k]>=-1e-7 for k in ['requested_energy_kwh','delivered_energy_kwh','grid_ev_energy_kwh','unmet_energy_kwh','pending_energy_kwh']), 'Invalid energy: '+rid)
        check(abs(m['requested_energy_kwh']-p['n']*p['energy'])<=1e-4, 'Requested fleet energy: '+rid)
        check(abs(m['requested_energy_kwh']-m['delivered_energy_kwh']-m['unmet_energy_kwh']-m['pending_energy_kwh'])<=1e-4, 'Energy conservation: '+rid)
        check(abs(m['grid_ev_energy_kwh']*.9-m['delivered_energy_kwh'])<=max(1e-4,m['delivered_energy_kwh']*1e-10), 'Grid/battery conversion: '+rid)
        check(m['pending_energy_kwh']<=1e-5, 'Pending departures: '+rid)
        check(m['grid_violation_steps']==sum(bool(t['violations']) for t in r['trace']), 'Violation trace consistency: '+rid)
        if r['status']=='passed':
            check(r['grid_ok'] and r['service_ok'] and m['grid_violation_steps']==0 and m['nonconverged_steps']==0 and m['unmet_energy_kwh']<=1e-5 and m['max_per_car_unmet_kwh']<=1e-6, 'False passing verdict: '+rid)
        key = dict(p); key.pop('strategy')
        paired.setdefault(digest(key),set()).add(r['session_hash'])
    check(all(len(h)==1 for h in paired.values()), 'Unpaired controller session hashes')
    for name, expected_count in [('baseline-index.json',42),('matrix-index.json',132),('edge-index.json',33)]:
        path = OUT/name
        if not path.exists(): pending.append(name); continue
        ids = read(path)
        check(bool(ids), 'Empty index: '+name)
        check(len(ids)==expected_count, 'Unexpected index coverage: '+name)
        for rid in ids: check(rid in current, 'Missing/current-revision indexed run: '+name+'/'+rid)
    capacity_path = OUT/'capacity.json'
    if not capacity_path.exists(): pending.append('capacity.json')
    else:
        capacities = read(capacity_path)
        if len(capacities)!=12: pending.append('capacity.json: expected12 completed scenario/policy groups')
        for row in capacities:
            attempts=row['attempts']
            for attempt in attempts:
                trials=[current.get(rid) for rid in attempt['run_ids']]
                check(len(trials)==3 and all(trials), 'Capacity missing three seed trials')
                if all(trials):
                    expected='unknown' if any(t['status']=='unknown' for t in trials) else 'passed' if all(t['status']=='passed' for t in trials) else 'failed'
                    check(attempt['status']==expected, 'Capacity aggregate verdict')
                    check({t['parameters']['seed'] for t in trials}==set(manifest['seeds']), 'Capacity seed coverage')
            passes=[a['n'] for a in attempts if a['status']=='passed']
            check(row['best_tested']==(max(passes) if passes else None), 'Incorrect capacity best-tested count')
            if row['next_failed'] is not None:
                check(any(a['n']==row['next_failed'] and a['status']=='failed' for a in attempts), 'Unmeasured capacity failure')
                check(row['next_failed']-row['best_tested']<=500, 'Capacity bracket exceeds stated500-car resolution')
    for filename in ['instantaneous.json','simultaneous.json','instantaneous-edges.json','invalid-inputs.json','admission-invalid-inputs.json']:
        if not (OUT/filename).exists(): pending.append(filename)
    if (OUT/'admission-invalid-inputs.json').exists():
        invalid=read(OUT/'admission-invalid-inputs.json')
        check({r['case'] for r in invalid}=={'unknown_node','negative_commitment','nan_commitment','bad_weights'}, 'Admission invalid-input coverage')
        check(all(r['rejected'] and r.get('error') for r in invalid),'Admission accepted invalid input')
    estimator_hash=sha(ROOT/'scripts'/'challenge_instant.py')
    for filename in ['instantaneous.json','simultaneous.json','instantaneous-edges.json']:
        if not (OUT/filename).exists(): continue
        for row in read(OUT/filename):
            check(row.get('runner_hash')==runner_hash, 'Estimator uses different main runner: '+filename)
            check(row.get('estimator_hash')==estimator_hash, 'Estimator source hash differs: '+filename)
        snapshot=FROZEN/'runners'/(estimator_hash+'.py')
        if not snapshot.exists(): pending.append('Estimator source snapshot')
        else: check(sha(snapshot)==estimator_hash,'Estimator source snapshot changed')
    if (OUT/'instantaneous-edges.json').exists():
        check(len(read(OUT/'instantaneous-edges.json'))==6,'Instantaneous edge-case coverage')
    if (OUT/'instantaneous.json').exists():
        rows=read(OUT/'instantaneous.json')
        if len(rows)!=204: pending.append('instantaneous.json: expected204 time/location/month rows')
        for i,row in enumerate(rows):
            if row['baseline']['status']=='passed':
                check(row['verified']['status']=='passed', 'Unverified instantaneous lower bound')
                if row.get('first_failed_kw') is not None: check(row.get('next_state') is not None and row['next_state']['status']=='failed' and row['first_failed_kw']>row['safe_kw'], 'Incorrect instantaneous upper bound')
            else: check(row['safe_kw']==0, 'Positive admission on unsafe/unknown baseline')
            if ac and i in (0,72,96,102,178,198):
                blocks=read(FROZEN/'blocks.json')
                candidates=[b for b in blocks if b.get('kind')!='public_hub' and (row['placement']=='city' or b.get('district_id',b.get('delivery_id'))==row['placement'])]
                # District membership is authoritative in the frozen district inventory.
                if row['placement']!='city':
                    ids=next(d['block_ids'] for d in read(FROZEN/'districts.json') if d['id']==row['placement'])
                    candidates=[b for b in blocks if b.get('kind')!='public_hub' and b['id'] in ids]
                total=sum(b['base_weight'] for b in candidates)
                weights={b['id']:b['base_weight']/total for b in candidates}
                evaluated=independent_ac(fixtures[row['fixture']],row['hour'],weights,row['safe_kw'])
                check(evaluated['status']==row['verified']['status'], 'Independent AC disagreement at row'+str(i))
                spot_checks.append({'row':i,'side':'lower' if row['baseline']['status']=='passed' else 'unsafe_baseline','fixture':row['fixture'],'hour':row['hour'],'power_kw':row['safe_kw'],'independent':evaluated,'saved_status':row['verified']['status']})
                if row.get('first_failed_kw') is not None:
                    failed=independent_ac(fixtures[row['fixture']],row['hour'],weights,row['first_failed_kw'])
                    check(failed['status']=='failed','Independent AC failed-bound disagreement at row'+str(i))
                    spot_checks.append({'row':i,'side':'upper','fixture':row['fixture'],'hour':row['hour'],'power_kw':row['first_failed_kw'],'independent':failed,'saved_status':'failed'})
    if (OUT/'simultaneous.json').exists():
        rows=read(OUT/'simultaneous.json')
        if len(rows)!=15: pending.append('simultaneous.json: expected15 power/location/time cases')
        for row in rows:
            if row['baseline']['status']=='passed':
                check(row['safe']['status']=='passed', 'Unverified simultaneous safe count')
                if row.get('next') and row['next']['status']=='failed': check(row['next_count']==row['safe_count']+1, 'Nonadjacent simultaneous bracket')
                else: warnings.append('Simultaneous result is ceiling or unknown; must not claim exact threshold')
            else: check(row['safe_count']==0, 'Positive simultaneous count on unsafe baseline')
    if require_complete: errors.extend('Missing completed evidence: '+x for x in pending)
    report={'status':'FAIL' if errors else 'INCOMPLETE' if pending else 'PASS','reviewer':'Independent code/evidence reviewer; no study-runner import','runner_hash':runner_hash,'current_runs':len(current),'historical_runs':len(runs)-len(current),'fixtures':len(fixtures),'source_photo_monthly_sums':{y:sum(v) for y,v in PHOTO.items()},'printed_totals':manifest['printed_annual_mwh'],'errors':errors,'pending':pending,'warnings':warnings,'independent_ac_checks':spot_checks}
    (OUT/'independent-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return bool(errors)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-complete',action='store_true')
    parser.add_argument('--ac',action='store_true')
    options=parser.parse_args()
    raise SystemExit(audit(options.require_complete,options.ac))
