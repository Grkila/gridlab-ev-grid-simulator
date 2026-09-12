"""Run the built frontend against a real isolated backend; no benchmark/RL jobs."""
import os, sys, json, threading, subprocess, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name]='1'
os.environ.pop('EV_PLAYGROUND_BROKER_URL',None)
from mvgrid.novi_sad.playground_app.server import create_server
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.benchmark import BenchmarkService

if __name__=='__main__':
    out=ROOT/'artifacts/handoff/e2e';out.mkdir(parents=True,exist_ok=True)
    runtime=Path(tempfile.mkdtemp(prefix='runtime-',dir=out))
    service=Service(runtime)
    saved=service.save_experiment({
        'name':'June whole-day comparison fixture',
        'hypothesis':'Verify the complete application workflow with twelve vehicles.',
        'operating_mode':'regulated',
        'demand':{'month':6,'monthly_energy':76000,'days_per_month':30},
        'fleet':{'fleet_size':12,'charging_profile':'whole_day',
                 'location_mix':{'residential':0.7,'workplace':0.2,'public':0.1}},
        'strategies':['immediate'],'seeds':[41001],
        'stop_on_violation':False,'stress_first':False,'max_runtime_seconds':300})
    state=service.start_run(saved['experiment_id'])
    deadline=time.monotonic()+330
    while state['status'] in ('starting','running'):
        if time.monotonic()>deadline:
            service.cancel_run(state['run_id'])
            raise TimeoutError('The twelve-vehicle fixture exceeded its time limit.')
        time.sleep(1)
        state=service.get_run(state['run_id'])
    if state['status']!='completed': raise RuntimeError(state)
    BenchmarkService(runtime).create_suite({'name':'Whole-day verification fixture',
        'charging_profile':'whole_day','standard_fleet':12,'max_fleet':32,
        'seeds':[41001],'operating_mode':'regulated'})
    server=create_server(0,runtime)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    env={**os.environ,'E2E_URL':f'http://127.0.0.1:{server.server_port}','E2E_OUT':str(out)}
    print('Isolated API:',env['E2E_URL'],flush=True)
    try:
        result=subprocess.run(['node',str(ROOT/'scripts/verify_api_e2e.cjs')],cwd=ROOT,env=env)
        (out/'runtime.json').write_text(json.dumps({'runtime':str(runtime),'exit_code':result.returncode},indent=2))
    finally:
        server.shutdown();server.server_close();thread.join()
    sys.exit(result.returncode)
