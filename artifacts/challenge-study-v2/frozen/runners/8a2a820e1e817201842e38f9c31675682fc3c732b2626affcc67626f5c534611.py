"""Frozen, direct-Python challenge study. No services, MCP calls or RL execution.

Run with the repository Python: scripts/challenge_study.py prepare|baseline|matrix|capacity|instant|edges|verify.
Every result is a separate atomic JSON file; reruns reuse only identical frozen inputs.
"""
from pathlib import Path
import os, sys, json, hashlib, shutil, calendar, random, time, math, argparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/challenge-study-v2'
FROZEN = OUT / 'frozen'
RUNNER_HASH=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
os.environ['MVGRID_ROOT'] = str(ROOT)
for thread_variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[thread_variable]='1'
sys.path.insert(0, str(FROZEN / 'src' if (FROZEN / 'src').exists() else ROOT / 'src'))
import numpy as np
import pandapower as pp
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.demand import generate_demand, allocate_block_demand
from mvgrid.novi_sad.playground.simulation import Simulator, simulate_case
from mvgrid.novi_sad.playground.districts import resolve_districts, district_id
from mvgrid.novi_sad.playground.loss_accounting import reconcile_supply
from mvgrid.novi_sad.playground.operating_scenario import apply_demand_scenario
from mvgrid.novi_sad.playground.capacity_layers import capacity_layers

MONTHLY = {
  2024: [113883,105207,100219,88797,76792,74739,78034,76745,82901,95688,106247,120553],
  2025: [116985,108060,102944,91743,79361,76965,80282,78409,84928,98283,109459,124221],
}
SEEDS = [61001,61002,61003]
STRATEGIES = ['immediate','fixed_delay','randomized_delay','capacity_aware','least_laxity_first','valley_filling']

def digest(x): return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(f'.{os.getpid()}.tmp'); tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8'); tmp.replace(p)

def prepare():
    if (FROZEN/'manifest.json').exists():
        print('Existing frozen study retained.'); return
    FROZEN.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'src', FROZEN/'src', ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)
    net,blocks=build_network()
    for mode in ['as_supplied','voltage_only','regulated']:
        model=__import__('copy').deepcopy(net)
        if mode!='as_supplied': model.ext_grid.vm_pu=1.04
        model['operating_scenario']=dict(mode=mode,source_voltage_pu=float(model.ext_grid.vm_pu.iloc[0]),baseline_peak_cap_kw=220000 if mode=='regulated' else None)
        pp.to_json(model,str(FROZEN/f'{mode}.json'))
    write(FROZEN/'blocks.json',blocks)
    write(FROZEN/'districts.json',resolve_districts(blocks))
    sources={str(p.relative_to(FROZEN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN.rglob('*') if p.is_file()}
    write(FROZEN/'manifest.json',dict(source_hashes=sources,python=sys.version,dependencies={k:__import__(k).__version__ for k in ['numpy','pandas','pandapower','scipy']},monthly_mwh=MONTHLY,printed_annual_mwh={'2024':1116804,'2025':1147635},seeds=SEEDS,network=dict(buses=len(net.bus),lines=len(net.line),transformers=len(net.trafo),blocks=len(blocks),sources=len(net.ext_grid),source_voltage_pu=list(net.ext_grid.vm_pu)),notes=['Photo monthly entries transcribed literally; row-sum discrepancies are preserved.','Primary study uses unchanged as-supplied 1.02 pu sources and no baseline shifting.','One synthetic session per vehicle; this measures daily charging participation, not registered city fleet.','No physical socket limits, LV feeder voltage, protection or N-1 guarantee.']))
    write(OUT/'protocol.json',dict(monthly_mwh=MONTHLY,seeds=SEEDS,limits={'min_voltage_pu':.95,'max_voltage_pu':1.05,'max_loading_percent':100},fleet_resolution=500,capacity_ladder=[0,1000,5000,10000,20000,40000,80000],primary_strategies=STRATEGIES,assumptions={'efficiency':.9,'battery_kwh':14,'charger_kw':7.4,'lv_baseline_fraction':.5,'lv_ev_fraction':1.,'dt_hours':.25,'horizon_steps':132,'home_window':'17:00-21:00 arrival; next-day09:00 departure','work_window':'08:00-10:00 arrival;17:00 departure','public_window':'08:00-20:00 arrival;3hour dwell','public_hubs':'ten illustrative hubs; no verified socket inventory','reserve':'last25percent usable;100percent rating is limit'}))
    print(json.dumps({'monthly_sums':{y:sum(v) for y,v in MONTHLY.items()},'frozen':str(FROZEN)}),flush=True)

def fixture(year=2025,month=6,stress=1.,mode='as_supplied',shape='normal'):
    key=f'{year}-{month:02d}-{stress:g}-{mode}-{shape}'
    path=OUT/'fixtures'/f'{key}.json'
    if path.exists(): return read(path)
    blocks=read(FROZEN/'blocks.json'); net=pp.from_json(str(FROZEN/f'{mode}.json'))
    profile=generate_demand(dict(month=month,monthly_energy=MONTHLY[year][month-1],days_per_month=calendar.monthrange(year,month)[1],days=2))
    profile=[x*stress for x in profile]
    if shape=='flat': profile=[sum(profile[:96])/96]*192
    if shape=='sharp':
        a=np.array(profile[:96]); a=a.mean()+(a-a.mean())*1.25; profile=a.tolist()*2
    raw=profile[:]
    if mode=='regulated': profile=apply_demand_scenario(profile,'regulated')
    gross=profile[:132]; allocation=allocate_block_demand(gross,blocks,{})
    net_alloc,recon=reconcile_supply(net,blocks,allocation)
    result=dict(id=key,year=year,month=month,mode=mode,stress=stress,shape=shape,gross_kw=gross,net_kw=[sum(x[t] for x in net_alloc.values()) for t in range(132)],allocation=net_alloc,reconciliation=recon,daily_kwh=sum(profile[:96])*.25,expected_daily_kwh=MONTHLY[year][month-1]*1000/calendar.monthrange(year,month)[1]*stress,shifted_kwh=sum(max(0,a-b) for a,b in zip(raw[:96],profile[:96]))*.25,original_peak_kw=max(raw[:96]),peak_kw=max(profile[:96]))
    result['hash']=digest(result); write(path,result); return result

POOL={}
def pool(seed,size,location='home',charger=7.4,energy=14.,district=None,dwell=12,timing_only=False,synchronized=False):
    key=(seed,location,charger,energy,district,dwell,timing_only,synchronized)
    rows=POOL.setdefault(key,[]); blocks=read(FROZEN/'blocks.json')
    ordinary=sorted([b for b in blocks if b.get('kind')!='public_hub' and (district is None or district_id(b)==district)],key=lambda b:b['id'])
    hubs=sorted([b for b in blocks if b.get('kind')=='public_hub' and (district is None or district_id(b)==district)],key=lambda b:b['id'])
    for i in range(len(rows),size):
        rng=random.Random(f'challenge-v1:{seed}:{i}')
        loc=rng.choices(['home','work','public'],[.7,.2,.1])[0] if location=='mixed' else location
        candidates=hubs if loc=='public' and not timing_only else ordinary
        weights=[max(b['base_weight'],0) for b in candidates]
        b=rng.choices(candidates,weights=weights if sum(weights) else None)[0]
        if loc=='home': arrival=72 if synchronized else rng.randrange(68,85); departure=132
        elif loc=='work': arrival=rng.randrange(32,41); departure=68
        else: arrival=rng.randrange(32,81); departure=arrival+dwell
        rows.append(dict(id=f'car-{i:06d}',block_id=b['id'],arrival_step=arrival,departure_step=departure,energy_kwh=energy,charger_kw=charger,efficiency=.9,location_type=loc))
    return rows[:size]

def case_for(f,strategy='immediate',lv=.5,district_factor=1.):
    districts=read(FROZEN/'districts.json')
    for d in districts: d['capacity_kw']*=district_factor
    return dict(strategy=strategy,seed=0,network_path=str(FROZEN/f"{f['mode']}.json"),blocks=read(FROZEN/'blocks.json'),resolved_districts=districts,block_demand_kw=f['allocation'],demand_measurement='load',network_capacity={'lv_baseline_fraction':lv,'lv_ev_fraction':1.},stop_on_violation=False,aggregate_ev_nodes=True,limits={'min_voltage_pu':.95,'max_voltage_pu':1.05,'max_loading_percent':100},strategy_options={'solver_seconds':2.,'max_variables':30000,'forecast':'persistence','valley_iterations':8})

def summarize(result,f,sessions):
    intervals=result['intervals']; m=result['metrics']; complete=result['complete'] and len(intervals)==132
    valid=complete and all(i['converged'] and all(i.get(k) is not None and math.isfinite(i[k]) for k in ['supply_kw','min_voltage_pu','max_voltage_pu','max_line_loading_percent','max_transformer_loading_percent']) for i in intervals)
    kinds=sorted({v['kind'] for i in intervals for v in i['violations']}); grid_ok=valid and not kinds
    per_car_max=max((s['remaining_kwh']/s.get('vehicle_count',1) for s in result['sessions']),default=0)
    service_ok=m['pending_energy_kwh']<=1e-5 and m['unmet_energy_kwh']<=1e-5 and per_car_max<=1e-6 and abs(m['requested_energy_kwh']-m['delivered_energy_kwh']-m['unmet_energy_kwh']-m['pending_energy_kwh'])<=1e-4
    impossible=sum(s['energy_kwh']>s['charger_kw']*s['efficiency']*.25*(s['departure_step']-s['arrival_step'])+1e-8 for s in sessions)
    m.update(supply_peak_kw=max((i['supply_kw'] for i in intervals if i['supply_kw'] is not None),default=None),ev_peak_kw=max(i['ev_kw'] for i in intervals),grid_violation_steps=sum(bool(i['violations']) for i in intervals),max_per_car_unmet_kwh=per_car_max,physically_impossible_sessions=impossible,safety_intervals=sum(i['safety_iterations']>0 for i in intervals),fallback_intervals=sum(bool(i.get('controller',{}).get('fallback')) for i in intervals),supply_energy_kwh=sum(i['supply_kw']*.25 for i in intervals if i['supply_kw'] is not None),baseline_supply_energy_kwh=sum(f['gross_kw'])*.25,baseline_reconciliation_max_error_kw=max(abs(x['error_kw']) for x in f['reconciliation']))
    first=next((dict(step=i['step'],violations=i['violations'][:8]) for i in intervals if i['violations']),None)
    return dict(status='passed' if grid_ok and service_ok else 'failed' if valid else 'unknown',complete=complete,grid_ok=grid_ok,service_ok=service_ok,violation_kinds=kinds,first_violation=first,metrics=m,trace=[dict(step=i['step'],supply_kw=i['supply_kw'],baseline_kw=f['gross_kw'][i['step']],ev_kw=i['ev_kw'],min_voltage_pu=i['min_voltage_pu'],charging_count=sum(b['counts']['charging'] for b in i['blocks']),violations=len(i['violations'])) for i in intervals])

def run(f,n=0,strategy='immediate',seed=61001,location='home',charger=7.4,energy=14.,district=None,lv=.5,district_factor=1.,dwell=12,timing_only=False,synchronized=False,keep=False):
    snapshot=FROZEN/'runners'/f'{RUNNER_HASH}.py'
    if not snapshot.exists(): snapshot.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(Path(__file__),snapshot)
    params=dict(runner_hash=RUNNER_HASH,fixture=f['id'],fixture_hash=f['hash'],n=n,strategy=strategy,seed=seed,location=location,charger=charger,energy=energy,district=district,lv=lv,district_factor=district_factor,dwell=dwell,timing_only=timing_only,synchronized=synchronized)
    rid=digest(params)[:20]; path=OUT/'runs'/f'{rid}.json'
    if path.exists() and not keep: return read(path)
    sessions=pool(seed,n,location,charger,energy,district,dwell,timing_only,synchronized)
    case=case_for(f,strategy,lv,district_factor); case['seed']=seed
    start=time.perf_counter()
    result=simulate_case(case,f['net_kw'],sessions)
    summary=summarize(result,f,sessions); summary.update(id=rid,parameters=params,session_hash=digest(sessions),elapsed_seconds=time.perf_counter()-start)
    write(path,summary)
    if keep: write(OUT/'detailed-inputs'/f'{rid}.json',result)
    print(json.dumps(dict(id=rid,fixture=f['id'],n=n,strategy=strategy,seed=seed,location=location,status=summary['status'],peak_mw=round(summary['metrics']['supply_peak_kw']/1000,3),unmet=round(summary['metrics']['unmet_energy_kwh'],3),seconds=round(summary['elapsed_seconds'],2))),flush=True)
    return summary

def baselines():
    rows=[]
    for year in [2024,2025]:
        for month in range(1,13):
            f=fixture(year,month); r=run(f); rows.append(r['id'])
    for mode in ['as_supplied','voltage_only','regulated']:
        for month in [1,6,12]:
            for stress in [1.,1.2]: rows.append(run(fixture(2025,month,stress,mode))['id'])
    write(OUT/'baseline-index.json',rows)

def matrix():
    rows=[]
    # Home strategy comparison. Daytime delay policies are deliberately not ranked.
    for mode,month,stress,n in [('as_supplied',6,1.,1000),('as_supplied',6,1.,10000),('as_supplied',12,1.,1000),('regulated',12,1.2,10000)]:
        f=fixture(2025,month,stress,mode)
        for seed in SEEDS:
            for strategy in STRATEGIES: rows.append(run(f,n,strategy,seed)['id'])
    # Same charger/battery demand; physical site and availability archetypes vary.
    for month in [6,12]:
        f=fixture(2025,month)
        for seed in SEEDS:
            for loc in ['home','work','public','mixed']:
                for strategy in ['immediate','capacity_aware']:
                    rows.append(run(f,1000,strategy,seed,loc)['id'])
    # Timing-only control keeps the ordinary-node distribution.
    for seed in SEEDS:
        for loc in ['work','public']:
            for strategy in ['immediate','capacity_aware']:
                rows.append(run(fixture(),1000,strategy,seed,loc,timing_only=True)['id'])
    write(OUT/'matrix-index.json',rows)

def capacity():
    records=[]
    scenarios=[('as_supplied',6,1.,'home',None),('as_supplied',12,1.,'home',None),('regulated',12,1.2,'home',None),('as_supplied',6,1.,'work',None),('as_supplied',6,1.,'public',None),('as_supplied',6,1.,'home','TELEP')]
    for mode,month,stress,loc,district in scenarios:
        f=fixture(2025,month,stress,mode)
        for strategy in ['immediate','capacity_aware']:
            tested={}
            def evaluate(n):
                trials=[run(f,n,strategy,seed,loc,district=district) for seed in SEEDS]
                status='unknown' if any(t['status']=='unknown' for t in trials) else 'passed' if all(t['status']=='passed' for t in trials) else 'failed'
                tested[n]=dict(n=n,status=status,run_ids=[t['id'] for t in trials]); return status
            baseline_status=evaluate(0)
            for n in ([1000] if baseline_status!='passed' else [1000,5000,10000,20000,40000,80000]): evaluate(n)
            passes=[n for n,r in tested.items() if r['status']=='passed']; best=max(passes) if passes else None
            fail=sorted(n for n,r in tested.items() if r['status']=='failed' and best is not None and n>best)
            if best is not None and fail:
                low,high=best,fail[0]
                while high-low>500:
                    middle=((low+high)//1000)*500
                    if middle<=low: middle=low+500
                    status=evaluate(middle)
                    if status=='passed': low=middle
                    elif status=='failed': high=middle
                    else: break
            passes=[n for n,r in tested.items() if r['status']=='passed']; best=max(passes) if passes else None
            record=dict(fixture=f['id'],strategy=strategy,location=loc,district=district,best_tested=best,next_failed=min((n for n,r in tested.items() if r['status']=='failed' and best is not None and n>best),default=None),baseline_status=tested[0]['status'],attempts=sorted(tested.values(),key=lambda x:x['n']),interpretation='Largest passing sampled fleet across three seeds; local bracket, not global maximum.')
            records.append(record); write(OUT/'capacity.json',records)

STATIC_NET={}
def static_state(f,step,weights,power_kw,lv=.5,margin=1.):
    if f['mode'] not in STATIC_NET: STATIC_NET[f['mode']]=pp.from_json(str(FROZEN/f"{f['mode']}.json"))
    net=STATIC_NET[f['mode']]; blocks=read(FROZEN/'blocks.json'); baseline={b['id']:f['allocation'][b['id']][step] for b in blocks}; ev={b['id']:power_kw*weights.get(b['id'],0) for b in blocks}
    for b in blocks:
        p=(baseline[b['id']]+ev[b['id']])/1000; net.load.loc[b['load_index'],['p_mw','q_mvar']]=[p,p*math.tan(math.acos(.97))]
    try: pp.runpp(net,numba=False,max_iteration=40,init='auto')
    except pp.LoadflowNotConverged: return dict(status='unknown',reasons=['nonconvergence'])
    if not all(np.isfinite(values).all() for values in [net.res_bus.vm_pu.values,net.res_line.loading_percent.values,net.res_trafo.loading_percent.values,net.res_ext_grid.p_mw.values]):
        return dict(status='unknown',reasons=['nonfinite electrical result'])
    stages=capacity_layers(net,blocks,baseline,ev,{'lv_baseline_fraction':lv,'lv_ev_fraction':1.},float(net.res_ext_grid.p_mw.sum())*1000)
    reasons=[]
    if net.res_bus.vm_pu.min()<.95: reasons.append('undervoltage:'+str(net.bus.at[net.res_bus.vm_pu.idxmin(),'name']))
    if net.res_bus.vm_pu.max()>1.05: reasons.append('overvoltage')
    for label,table,res in [('line',net.line,net.res_line),('transformer',net.trafo,net.res_trafo)]:
        if res.loading_percent.max()>100*margin: reasons.append(label+':'+str(table.at[res.loading_percent.idxmax(),'name']))
    for s in stages:
        if s['demand_kw']>s['capacity_kw']*margin+1e-6: reasons.append('stage:'+s['id'])
    for d in read(FROZEN/'districts.json'):
        if sum(baseline[b]+ev[b] for b in d['block_ids'])>d['capacity_kw']*margin+1e-6: reasons.append('district:'+d['id'])
    return dict(status='failed' if reasons else 'passed',reasons=reasons,min_voltage_pu=float(net.res_bus.vm_pu.min()),max_line_loading_percent=float(net.res_line.loading_percent.max()),max_transformer_loading_percent=float(net.res_trafo.loading_percent.max()),supply_kw=float(net.res_ext_grid.p_mw.sum())*1000,stage_headroom_kw={s['id']:s['headroom_kw'] for s in stages})

def placement(kind='city'):
    blocks=read(FROZEN/'blocks.json'); candidates=[b for b in blocks if b.get('kind')!='public_hub' and (kind=='city' or district_id(b)==kind)]
    total=sum(b['base_weight'] for b in candidates)
    return {b['id']:b['base_weight']/total for b in candidates}

def instantaneous():
    records=[]
    for month in [6,12]:
        f=fixture(2025,month)
        for where in ['city','TELEP']:
            weights=placement(where)
            for step in range(0,96,4):
                start=time.perf_counter(); zero=static_state(f,step,weights,0)
                low=0.; high=500000.; probes=[{'kw':0,'state':zero}]
                upper=static_state(f,step,weights,high) if zero['status']=='passed' else zero
                if zero['status']=='passed' and upper['status']=='failed':
                    for _ in range(19):
                        mid=(low+high)/2; state=static_state(f,step,weights,mid); probes.append({'kw':mid,'state':state})
                        if state['status']=='passed': low=mid
                        elif state['status']=='failed': high=mid
                        else: break
                checked=static_state(f,step,weights,low)
                next_state=static_state(f,step,weights,high) if zero['status']=='passed' else zero
                records.append(dict(runner_hash=RUNNER_HASH,fixture=f['id'],hour=step/4,placement=where,baseline=zero,safe_kw=low,first_failed_kw=high if zero['status']=='passed' and next_state['status']=='failed' else None,upper_check=upper,verified=checked,next_state=next_state,elapsed_seconds=time.perf_counter()-start,full_power_equivalents={str(p):int(low//p) for p in [3.7,7.4,11,22,50]},probes=probes))
                write(OUT/'instantaneous.json',records)
                print(json.dumps({'instant':f['id'],'hour':step/4,'placement':where,'safe_mw':round(low/1000,3)}),flush=True)
    # Actual integer cars at prescribed nested locations, with fresh AC checks on both sides.
    boundaries=[]
    for month,step,where in [(6,12,'city'),(6,72,'city'),(6,80,'city'),(6,72,'TELEP'),(12,72,'city')]:
        f=fixture(2025,month)
        for charger in [7.4,22,50]:
            sessions=pool(61001,80000,district=None if where=='city' else where)
            def evaluate(n):
                counts={}
                for s in sessions[:n]: counts[s['block_id']]=counts.get(s['block_id'],0)+1
                weights={k:v/n for k,v in counts.items()} if n else placement(where)
                return static_state(f,step,weights,n*charger)
            lo=0; hi=80000; base=evaluate(0)
            upper=evaluate(hi) if base['status']=='passed' else base
            if base['status']=='passed' and upper['status']=='failed':
                while hi-lo>1:
                    mid=(hi+lo)//2; state=evaluate(mid)
                    if state['status']=='passed': lo=mid
                    elif state['status']=='failed': hi=mid
                    else: break
            else: hi=0
            boundaries.append(dict(runner_hash=RUNNER_HASH,fixture=f['id'],hour=step/4,placement=where,charger_kw=charger,seed=61001,safe_count=lo,next_count=hi,baseline=base,upper_check=upper,safe=evaluate(lo),next=evaluate(hi)))
    write(OUT/'simultaneous.json',boundaries)

def edges():
    rows=[]; f=fixture()
    for lv in [.3,.5,.7]:
        for seed in SEEDS: rows.append(run(f,10000,'capacity_aware',seed,lv=lv)['id'])
    for charger,energy in [(3.7,14),(11,14),(22,14),(7.4,7),(7.4,28),(7.4,0)]:
        rows.append(run(f,10000,'capacity_aware',charger=charger,energy=energy)['id'])
    for factor in [.8,1.2]: rows.append(run(f,5000,'capacity_aware',district='TELEP',district_factor=factor)['id'])
    for shape in ['flat','sharp']: rows.append(run(fixture(shape=shape),10000,'capacity_aware')['id'])
    for month in [6,12]: rows.append(run(fixture(2025,month,1147635/sum(MONTHLY[2025])),10000,'capacity_aware')['id'])
    for strategy in ['immediate','fixed_delay','randomized_delay','capacity_aware']:
        rows.append(run(f,10000,strategy,synchronized=True)['id'])
    for charger in [7.4,22,50]: rows.append(run(f,1000,'capacity_aware',location='public',charger=charger)['id'])
    rows.append(run(f,1000,'capacity_aware',location='public',dwell=4)['id'])
    rows.append(run(f,1000,'fixed_delay',location='work')['id'])
    for mode in ['as_supplied','voltage_only','regulated']:
        rows.append(run(fixture(2025,12,1.2,mode),10000,'capacity_aware')['id'])
    write(OUT/'edge-index.json',rows)
    # Explicit invalid-input behavior, without turning numerical errors into capacity failure.
    probes=[]
    for label,demand in [('zero_gross',[0.]*132),('negative_gross',[-1.]*132),('nan_gross',[float('nan')]*132)]:
        case=case_for(f); case.pop('block_demand_kw'); case['demand_measurement']='supply_including_losses'
        try: Simulator().reset(case,demand,[]); probes.append(dict(case=label,rejected=False))
        except Exception as e: probes.append(dict(case=label,rejected=True,error=type(e).__name__+': '+str(e)))
    write(OUT/'invalid-inputs.json',probes)

def verify():
    manifest=read(FROZEN/'manifest.json')
    bad=[name for name,h in manifest['source_hashes'].items() if hashlib.sha256((FROZEN/name).read_bytes()).hexdigest()!=h]
    fixtures=[read(p) for p in (OUT/'fixtures').glob('*.json')]
    runs=[read(p) for p in (OUT/'runs').glob('*.json')]
    violations=[]
    for f in fixtures:
        h=f.pop('hash'); assert digest(f)==h; f['hash']=h
        if abs(f['daily_kwh']-f['expected_daily_kwh'])>1e-5: violations.append(f['id']+' daily energy')
    for r in runs:
        m=r['metrics']
        if r['parameters'].get('runner_hash')!=RUNNER_HASH: continue
        if m['pending_energy_kwh']>1e-5: violations.append(r['id']+' pending departure')
        if r['status']=='passed' and (not r['grid_ok'] or not r['service_ok']): violations.append(r['id']+' false pass')
        if abs(m['requested_energy_kwh']-r['parameters']['n']*r['parameters']['energy'])>1e-4: violations.append(r['id']+' fleet energy')
        if abs(m['grid_ev_energy_kwh']*.9-m['delivered_energy_kwh'])>1e-4: violations.append(r['id']+' charger efficiency energy')
        if any(not math.isfinite(m[k]) or m[k]<-1e-8 for k in ['requested_energy_kwh','delivered_energy_kwh','unmet_energy_kwh','pending_energy_kwh','grid_ev_energy_kwh']): violations.append(r['id']+' invalid energy')
    pairs={}
    for r in runs:
        p=dict(r['parameters']); p.pop('strategy'); key=digest(p); pairs.setdefault(key,set()).add(r['session_hash'])
    if any(len(v)!=1 for v in pairs.values()): violations.append('Unmatched controller sessions')
    selected=[r for r in runs if r['parameters'].get('runner_hash')==RUNNER_HASH]
    for name in ['baseline-index.json','matrix-index.json','edge-index.json','capacity.json','instantaneous.json','simultaneous.json','invalid-inputs.json']:
        if not (OUT/name).exists(): violations.append('missing '+name)
    for name in ['baseline-index.json','matrix-index.json','edge-index.json']:
        if (OUT/name).exists():
            for rid in read(OUT/name):
                if not (OUT/'runs'/f'{rid}.json').exists() or read(OUT/'runs'/f'{rid}.json')['parameters'].get('runner_hash')!=RUNNER_HASH: violations.append('missing/current revision '+rid)
    report=dict(runner_hash=RUNNER_HASH,frozen_source_errors=bad,fixture_count=len(fixtures),run_count=len(selected),historical_nonfinal_runs=len(runs)-len(selected),passed=sum(r['status']=='passed' for r in selected),failed=sum(r['status']=='failed' for r in selected),unknown=sum(r['status']=='unknown' for r in selected),violations=violations,monthly_row_sums={y:sum(v) for y,v in MONTHLY.items()},maximum_reconciliation_error_kw=max((r['metrics']['baseline_reconciliation_max_error_kw'] for r in selected),default=0))
    write(OUT/'verification.json',report); print(json.dumps(report),flush=True)
    if bad or violations: raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['prepare','baseline','matrix','capacity','instant','edges','verify']); args=parser.parse_args()
    {'prepare':prepare,'baseline':baselines,'matrix':matrix,'capacity':capacity,'instant':instantaneous,'edges':edges,'verify':verify}[args.stage]()
