"""Run the built frontend against a real isolated backend; no benchmark/RL jobs."""
import os, sys, json, threading, subprocess, shutil, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name]='1'
os.environ.pop('EV_PLAYGROUND_BROKER_URL',None)
from mvgrid.novi_sad.playground_app.server import create_server

if __name__=='__main__':
    out=ROOT/'artifacts/playground/whole-day-study/e2e';out.mkdir(parents=True,exist_ok=True)
    runtime=Path(tempfile.mkdtemp(prefix='runtime-',dir=out))
    origin=ROOT/'artifacts/playground/whole-day-study/experiment-runtime'
    for kind in ('experiments','runs'): shutil.copytree(origin/kind,runtime/kind)
    source=ROOT/'artifacts/playground/whole-day-study/runtime'
    shutil.copytree(source/'benchmark-suites',runtime/'benchmark-suites')
    job='bench-1682223431ba4678'
    (runtime/'benchmarks'/job).mkdir(parents=True)
    for file in ('state.json','request.json','results.json'):
        shutil.copy2(source/'benchmarks'/job/file,runtime/'benchmarks'/job/file)
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
