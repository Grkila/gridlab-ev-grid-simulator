"""Run all seven non-RL algorithms on the whole-day standard suite locally."""
import os
from pathlib import Path
import sys
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
os.environ.pop('EV_PLAYGROUND_BROKER_URL',None)
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from mvgrid.novi_sad.playground.benchmark import BenchmarkService
from mvgrid.novi_sad.playground.service import write_json

if __name__=='__main__':
    out=ROOT/'artifacts/playground/whole-day-study'
    service=BenchmarkService(out/'runtime')
    suite=service.create_suite(dict(name='Whole-day charging: seven algorithms',charging_profile='whole_day',
        standard_fleet=500,max_fleet=50000,seeds=[41001],district='TELEP',operating_mode='regulated',
        search_mode='doubling',until_failure=True,aggregate_ev_nodes=True))
    job=service.start(suite['suite_id'],dict(strategies=['immediate','fixed_delay','randomized_delay','capacity_aware','least_laxity_first','valley_filling','voltage_responsive'],
        strategy_options=dict(solver_seconds=3,max_variables=30000,forecast='persistence',valley_iterations=8),
        max_runtime_seconds=21600,case_runtime_seconds=240))
    write_json(out/'launch.json',dict(suite=suite,job=job))
    print(job,flush=True)
