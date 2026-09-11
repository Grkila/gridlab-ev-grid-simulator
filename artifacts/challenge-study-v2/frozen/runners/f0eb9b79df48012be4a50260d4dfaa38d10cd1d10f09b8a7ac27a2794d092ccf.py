"""Allocation-specific instantaneous AC admission screen and full-rate car tests."""
from pathlib import Path
import sys, time, hashlib, json, math
sys.path.insert(0,str(Path(__file__).resolve().parent))
import challenge_study as s

VERSION=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def estimate(f,step,weights,committed=None,lv=.5,margin=1.):
    """Largest sampled safe incremental kW on fixed placement; sub-kW local bracket.

    A baseline violation gives no admission. Unknowns are never physical failures.
    Headroom is a steady-state screen, not a deadline-feasible charging schedule.
    """
    if not weights or any(not math.isfinite(v) or v<0 for v in weights.values()) or abs(sum(weights.values())-1)>1e-8:
        raise ValueError('Placement must have nonnegative weights summing to one')
    committed=committed or {}; started=time.perf_counter(); probes=[]
    def evaluate(additional):
        ev={b:max(0.,committed.get(b,0.))+additional*weights.get(b,0.) for b in set(weights)|set(committed)}
        total=sum(ev.values()); mix={b:p/total for b,p in ev.items()} if total else weights
        result=s.static_state(f,step,mix,total,lv,margin); probes.append(dict(kw=additional,state=result)); return result
    zero=evaluate(0); low=0.; high=None; bad=None
    if zero['status']=='passed':
        candidate=1000.
        while candidate<=512000:
            state=evaluate(candidate)
            if state['status']=='passed': low=candidate; candidate*=2
            else: high=candidate; bad=state; break
        if high is not None:
            while high-low>1.:
                mid=(low+high)/2; state=evaluate(mid)
                if state['status']=='passed': low=mid
                else: high=mid; bad=state
    safe=evaluate(low)
    return dict(runner_hash=s.RUNNER_HASH,estimator_hash=VERSION,fixture=f['id'],step=step,hour=step/4,weights=weights,committed_kw=committed,lv_fraction=lv,rating_fraction=margin,baseline=zero,safe_kw=low,first_failed_kw=high if bad and bad['status']=='failed' else None,unknown_upper_kw=high if bad and bad['status']=='unknown' else None,ceiling_reached=zero['status']=='passed' and high is None,verified=safe,next_state=bad,elapsed_seconds=time.perf_counter()-started,full_power_equivalents={str(p):int(low//p) for p in [3.7,7.4,11,22,50]},probes=probes)

def main():
    snapshots=[]
    for month in [6,12]:
        f=s.fixture(2025,month)
        for where in ['city','TELEP']:
            steps=range(96) if where=='city' else [0,12,32,48,72,80]
            for step in steps:
                r=estimate(f,step,s.placement(where)); r['placement']=where; snapshots.append(r)
            s.write(s.OUT/'instantaneous.json',snapshots)
            print(json.dumps(dict(month=month,placement=where,completed=len(snapshots))),flush=True)
    boundaries=[]
    for month,step,where in [(6,12,'city'),(6,72,'city'),(6,80,'city'),(6,72,'TELEP'),(12,72,'city')]:
        f=s.fixture(2025,month)
        for charger in [7.4,22.,50.]:
            cars=s.pool(61001,131072,district=None if where=='city' else where)
            def evaluate(n):
                counts={}
                for car in cars[:n]: counts[car['block_id']]=counts.get(car['block_id'],0)+1
                weights={k:v/n for k,v in counts.items()} if n else s.placement(where)
                return s.static_state(f,step,weights,n*charger)
            baseline=evaluate(0); low=0; high=None; upper=None; probes=[]
            if baseline['status']=='passed':
                n=1
                while n<=131072:
                    r=evaluate(n); probes.append(dict(n=n,status=r['status']))
                    if r['status']=='passed': low=n; n*=2
                    else: high=n; upper=r; break
                if high is not None:
                    while high-low>1:
                        n=(low+high)//2; r=evaluate(n); probes.append(dict(n=n,status=r['status']))
                        if r['status']=='passed': low=n
                        else: high=n; upper=r
            boundaries.append(dict(runner_hash=s.RUNNER_HASH,estimator_hash=VERSION,fixture=f['id'],hour=step/4,placement=where,charger_kw=charger,seed=61001,safe_count=low,next_count=high,baseline=baseline,safe=evaluate(low),next=evaluate(high) if high else None,ceiling_reached=baseline['status']=='passed' and high is None,probes=probes))
        s.write(s.OUT/'simultaneous.json',boundaries)
    edges=[]; f=s.fixture()
    for lv in [.3,.5,.7]:
        r=estimate(f,72,s.placement(),lv=lv); r['label']=f'LV baseline share {lv:g}'; edges.append(r)
    for fraction in [.8,1.2]:
        r=estimate(f,72,s.placement(),margin=fraction); r['label']=f'Adopted thermal/stage/district ratings x{fraction:g}'; edges.append(r)
    committed={k:1000*v for k,v in s.placement().items()}
    r=estimate(f,72,s.placement(),committed=committed); r['label']='1 MW already charging in same placement'; edges.append(r)
    s.write(s.OUT/'instantaneous-edges.json',edges)
    snapshot=s.FROZEN/'runners'/f'{VERSION}.py'; snapshot.write_bytes(Path(__file__).read_bytes())
    print('Instantaneous and integer full-power checks complete.',flush=True)

if __name__=='__main__': main()
