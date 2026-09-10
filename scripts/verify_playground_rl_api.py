"""Exercise real RL HTTP training, catalog, validation and cancellation in an isolated store."""
from pathlib import Path
import http.client
import json
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground_app.server import create_server
from mvgrid.novi_sad.playground.service import write_json


def main():
    with tempfile.TemporaryDirectory() as root:
        server = create_server(0,root)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        def request(path, body=None):
            conn = http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=30)
            conn.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),{'Content-Type':'application/json'})
            response = conn.getresponse(); status = response.status; data = json.loads(response.read()); conn.close()
            return status,data
        def wait_job(job):
            deadline = time.monotonic()+120
            while job['status'] in ('starting','running'):
                if time.monotonic()>deadline: raise TimeoutError(job)
                time.sleep(.2); status,job = request('/api/rl/jobs/'+job['job_id'])
                assert status==200,job
            return job
        try:
            status,source = request('/api/experiments',{'definition':{'name':'HTTP RL verification','hypothesis':'Real training lifecycle',
                'fleet':{'fleet_size':2},'demand':{'monthly_energy':50000},'strategies':['immediate']}})
            assert status==200,source
            status,error = request('/api/rl/train',{'experiment_id':source['experiment_id'],'config':{'reward':{'capacity':-1}}})
            assert status==400,error
            status,job = request('/api/rl/train',{'experiment_id':source['experiment_id'],'config':{'episodes':1,'seed':17000,'max_runtime_seconds':120}})
            assert status==200,job
            status,conflict = request('/api/runs',{'experiment_id':source['experiment_id']})
            assert status==400,conflict
            job = wait_job(job); assert job['status']=='completed',job
            status,catalog = request('/api/rl/catalog'); assert status==200 and len(catalog['models'])==1,catalog
            status,cancelled = request('/api/rl/train',{'experiment_id':source['experiment_id'],'config':{'episodes':20,'seed':18000,'max_runtime_seconds':120}})
            assert status==200,cancelled
            status,ack = request('/api/rl/jobs/'+cancelled['job_id']+'/cancel',{})
            assert status==200 and ack['cancel_requested'],ack
            cancelled = wait_job(cancelled); assert cancelled['status']=='cancelled' and cancelled['model_id'] is None,cancelled
            status,catalog = request('/api/rl/catalog'); assert len(catalog['models'])==1,catalog
            # Wait for worker processes to fully exit before deleting their temp store.
            import psutil
            for state in (job,cancelled):
                try: psutil.Process(state['pid']).wait(timeout=10)
                except psutil.NoSuchProcess: pass
            evidence = {'passed':True,'checks':['HTTP input validation','real completed training','model catalog','shared worker exclusion','HTTP cancellation','no model from cancelled job'],
                        'completed_episodes':job['completed_episodes'],'cancelled_status':cancelled['status']}
            write_json(REPOSITORY_ROOT/'artifacts/playground/evidence/rl_api.json',evidence)
            print(json.dumps(evidence,indent=2))
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__=='__main__': main()
