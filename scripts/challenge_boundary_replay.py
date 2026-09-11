"""Detailed AC replay near the observed June fleet boundaries."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import challenge_study as s
from mvgrid.novi_sad.playground.detailed import detailed_check

def main():
    rows=[]; previous={r['run_id']:r for r in s.read(s.OUT/'boundary-replay.json')} if (s.OUT/'boundary-replay.json').exists() else {}
    for n,strategy in [(48000,'capacity_aware'),(13500,'immediate')]:
        f=s.fixture(); summary=s.run(f,n,strategy,61003)
        if not (s.OUT/'detailed-inputs'/f"{summary['id']}.json").exists(): summary=s.run(f,n,strategy,61003,keep=True)
        result=s.read(s.OUT/'detailed-inputs'/f"{summary['id']}.json")
        steps=sorted({max(range(132),key=lambda t:result['intervals'][t]['supply_kw']),min(range(132),key=lambda t:result['intervals'][t]['min_voltage_pu'])})
        first=next((i['step'] for i in result['intervals'] if i['violations']),None)
        if first is not None: steps=sorted(set(steps)|{first})
        old=previous.get(summary['id']); observed={x['step'] for x in old['check']['snapshots']} if old else set()
        missing=[t for t in steps if t not in observed]
        check=detailed_check(result,missing) if missing else old['check']
        if old and missing: check['snapshots']=sorted(old['check']['snapshots']+check['snapshots'],key=lambda x:x['step'])
        rows.append(dict(run_id=summary['id'],fixture=f['id'],n=n,strategy=strategy,seed=61003,check=check))
        s.write(s.OUT/'boundary-replay.json',rows)
        print(f'Detailed boundary replay: {n} {strategy}',flush=True)

if __name__=='__main__': main()
