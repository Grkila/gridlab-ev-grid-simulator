"""Expose completed local study evidence in the main app without overwriting runs."""
from pathlib import Path
import json,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'artifacts/playground/whole-day-study'
DEST=ROOT/'artifacts/playground/runtime'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def copy(source,destination):
    if source.is_file():
        if destination.exists():
            assert source.read_bytes()==destination.read_bytes(),f'Existing evidence differs: {destination}'
        else:
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    else:
        for path in source.rglob('*'):
            if path.is_file():copy(path,destination/path.relative_to(source))

if __name__=='__main__':
    published=[]
    for row in read(STUDY/'experiment-validation.json'):
        origin=STUDY/'experiment-runtime'
        assert read(origin/'runs'/row['run_id']/'state.json')['status']=='completed'
        copy(origin/'experiments'/(row['experiment_id']+'.json'),DEST/'experiments'/(row['experiment_id']+'.json'))
        copy(origin/'runs'/row['run_id'],DEST/'runs'/row['run_id'])
        published.append(row['run_id'])
    launch=read(STUDY/'launch.json');suite=launch['suite']['suite_id'];job=launch['job']['job_id']
    copy(STUDY/'runtime/benchmark-suites'/suite,DEST/'benchmark-suites'/suite)
    status=read(STUDY/'runtime/benchmarks'/job/'state.json')['status']
    if status=='completed':
        copy(STUDY/'runtime/benchmarks'/job,DEST/'benchmarks'/job);published.append(job)
    record=dict(published=published,benchmark_status=status)
    (STUDY/'published.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(record)
