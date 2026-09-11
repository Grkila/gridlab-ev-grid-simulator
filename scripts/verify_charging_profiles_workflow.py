"""Real saved experiments through the local worker, without MCP or RL."""
import os,sys,time
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ.pop('EV_PLAYGROUND_BROKER_URL',None)
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from mvgrid.novi_sad.playground.service import Service,read_json,write_json
from mvgrid.novi_sad.playground.benchmark import trial_summary

if __name__=='__main__':
    out=ROOT/'artifacts/playground/whole-day-study'
    svc=Service(out/'experiment-runtime');records=[]
    for profile in ('home_only','whole_day'):
        saved=svc.save_experiment(dict(name='Schedule example: '+profile,hypothesis='All requested energy can be delivered for this small reference fleet.',
            case_origin='llm',operating_mode='regulated',demand=dict(month=6,monthly_energy=76000,days_per_month=30,days=1),
            fleet=dict(charging_profile=profile,fleet_size=100),strategies=['immediate','capacity_aware'],seeds=[41001],
            stop_on_violation=False,stress_first=False,max_runtime_seconds=600,
            assertions=[dict(type='hard',metric='unmet_energy_kwh',operator='le',value=1e-5)]))
        job=svc.start_run(saved['experiment_id'])
        print(profile,job,flush=True)
        while True:
            state=svc.get_run(job['run_id'])
            if state['status'] not in ('starting','running'):break
            time.sleep(2)
        assert state['status']=='completed',state
        folder=svc._path('runs',job['run_id']);manifest=read_json(folder/'manifest.json')
        cases=[read_json(p) for p in (folder/'cases').glob('*.json')]
        assert len(cases)==2
        for case in cases:
            assert trial_summary(case)['status']=='passed',case['metrics']
        record=dict(profile=profile,experiment_id=saved['experiment_id'],run_id=job['run_id'],
                    steps=len(manifest['demand_kw']),cases=[dict(strategy=c['strategy'],delivered_kwh=c['metrics']['delivered_energy_kwh'],unmet_kwh=c['metrics']['unmet_energy_kwh']) for c in cases])
        records.append(record);write_json(out/'experiment-validation.json',records)
        print(record,flush=True)
