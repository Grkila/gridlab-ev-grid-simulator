"""Real HTTP benchmark acceptance on a bounded, explicitly labelled fixture."""
from pathlib import Path
import argparse
import json
import sys
import time
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.service import write_json


def main(url):
    def call(path, body=None):
        request = Request(url+path, data=None if body is None else json.dumps(body).encode(),
                          headers={'Content-Type':'application/json'})
        with urlopen(request, timeout=60) as response: return json.load(response)
    catalog = call('/api/benchmarks')
    assert len(catalog['tests']) == 10
    suite = call('/api/benchmarks/suites', {'definition':dict(name='Verification · 10-car ceiling (not capacity study)',
                  standard_fleet=10, max_fleet=10, seeds=[41001])})
    job = call('/api/benchmarks/jobs', {'suite_id':suite['suite_id'], 'config':dict(
        strategies=['immediate','capacity_aware','mpc'],max_runtime_seconds=1000,case_runtime_seconds=120)})
    print(json.dumps(dict(job_id=job['job_id'],suite_id=suite['suite_id'])), flush=True)
    deadline = time.monotonic()+1060
    while True:
        data = call('/api/benchmarks/jobs/'+job['job_id'])
        state = data['job']
        if state['status'] not in ('starting','running'): break
        if time.monotonic()>deadline: raise TimeoutError(state)
        print(json.dumps({k:state.get(k) for k in ('status','current_test','current_strategy','current_fleet','completed_rows','current_step')}),flush=True)
        time.sleep(10)
    assert state['status']=='completed', state
    assert data['complete'] and len(data['rows'])==30, state
    assert data['common_fleet'] is not None, 'This small common fleet should be served by all three controllers.'
    hashes = {}
    for row in data['rows']:
        assert row['status'] not in ('error','incomplete'), row
        for attempt in row.get('attempts', [row]):
            assert attempt['status'] not in ('error','incomplete'), attempt
            for trial in attempt.get('trials',[]):
                key = (row['test_id'],attempt['fleet_size'],trial['seed'])
                hashes.setdefault(key,set()).add((trial['demand_hash'],trial['replay_hash']))
    assert all(len(values)==1 for values in hashes.values()), 'Algorithms did not receive matching replays.'
    comparison = call('/api/benchmarks/suites/'+suite['suite_id']+'/compare')
    assert len([r for r in comparison['rows'] if r['job_id']==job['job_id']])==27
    # Actual cancellation and shared-lock lifecycle, without another full study.
    cancelled = call('/api/benchmarks/jobs', {'suite_id':suite['suite_id'],'config':dict(strategies=['immediate'],max_runtime_seconds=60)})
    ack = call('/api/benchmarks/jobs/'+cancelled['job_id']+'/cancel', {})
    assert ack['cancel_requested']
    until = time.monotonic()+30
    while True:
        stopped = call('/api/benchmarks/jobs/'+cancelled['job_id'])
        if stopped['job']['status'] not in ('starting','running'): break
        assert time.monotonic()<until
        time.sleep(.2)
    assert stopped['job']['status']=='cancelled' and not stopped['complete']
    evidence = dict(status='passed',scope='Bounded workflow verification; ten-car ceiling is not maximum city capacity.',
                    suite=suite, job=state, common_fleet=data['common_fleet'],
                    rows=data['rows'], matched_replays=True,cancellation=stopped['job']['status'])
    write_json(REPOSITORY_ROOT/'artifacts/playground/evidence/benchmark_verification.json',evidence)
    print(json.dumps(dict(status='passed',job_id=job['job_id'],rows=len(data['rows']),common_fleet=data['common_fleet'])),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--url',default='http://127.0.0.1:8532')
    main(parser.parse_args().url.rstrip('/'))
