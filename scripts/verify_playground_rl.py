"""Real bounded train/evaluate workflow; saves measured evidence, never asserts superiority."""
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.service import Service, write_json, read_json
from mvgrid.novi_sad.playground.rl_service import RLService


def main():
    service = Service(); rl = RLService(service.root)
    source = service.save_experiment({'name':'RL randomized-day verification',
        'hypothesis':'Learn binary charging and measure held-out service and constraints against baselines.',
        'demand':{'monthly_energy':76000,'month':6,'days_per_month':30,'randomize':True},
        'fleet':{'fleet_size':24},'strategies':['immediate','capacity_aware'], 'seeds':[701,702],
        'assertions':[{'type':'paired','metric':'peak_demand_kw','reduction_fraction':0.,'control':'immediate','candidate':'capacity_aware'}],
        'stop_on_violation':False,'stress_first':False,'max_runtime_seconds':900})
    job = rl.start(source['experiment_id'],{'episodes':4,'seed':12000,'max_runtime_seconds':900})
    print('TRAIN',job['job_id'],flush=True)
    while job['status'] in ('starting','running'):
        time.sleep(2); job = rl.get_job(job['job_id'])
    if job['status']!='completed': raise RuntimeError(job)
    model = rl.get_model(job['model_id'])
    payload = model['payload']
    if payload['initial_policy_hash']==payload['final_policy_hash']: raise AssertionError('No policy learning occurred')
    if len({r['demand_hash'] for r in job['history']})!=4: raise AssertionError('Training days did not vary')
    print('MODEL',job['model_id'],flush=True)
    definition = source['definition']
    definition.update(name='RL held-out comparison',strategies=['immediate','capacity_aware','rl'],assertions=[],
                      rl={'model_id':job['model_id']})
    saved = service.save_experiment(definition)
    state = service.start_run(saved['experiment_id'])
    print('RUN',state['run_id'],flush=True)
    while state['status'] in ('starting','running'):
        time.sleep(2); state = service.get_run(state['run_id'])
    results = service.get_results(state['run_id'])
    if state['status']!='completed': raise RuntimeError(state)
    for seed in definition['seeds']:
        cases = [c for c in results['cases'] if c['seed']==seed]
        if len({c['demand_hash'] for c in cases})!=1: raise AssertionError('Unpaired demand curves')
        if any(c['metrics']['pending_energy_kwh']>1e-6 or not c['complete'] for c in cases): raise AssertionError('Incomplete departure coverage')
    rows = [{k:c[k] for k in ('case_id','strategy','seed','metrics')} for c in results['cases']]
    evidence = {'training_job':job,'model_id':job['model_id'],'evaluation_run_id':state['run_id'],
                'cases':rows,'checks':{'weights_changed':True,'randomized_days':True,'paired_heldout_demand':True,'departure_coverage':True},
                'interpretation':'Functional verification with four training episodes; not evidence of convergence or superiority.'}
    write_json(REPOSITORY_ROOT/'artifacts/playground/evidence/rl_verification.json',evidence)
    for row in rows: print(row['strategy'],row['seed'],row['metrics'],flush=True)


if __name__=='__main__': main()
