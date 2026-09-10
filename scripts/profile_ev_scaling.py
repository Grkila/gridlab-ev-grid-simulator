"""Diagnostic snapshot timings, not hosting-capacity experiment evidence."""
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import pandapower as pp
from mvgrid.novi_sad.playground.benchmark import BenchmarkService,session_pool
from mvgrid.novi_sad.playground.simulation import Simulator
from mvgrid.novi_sad.playground.strategies import create_controller

service=BenchmarkService()
sid='suite-40cbac52af3664f7d5b3'
fixture=service.get_suite(sid)
aggregate='--aggregate' in sys.argv
output=ROOT/'artifacts/playground'/('ev-scaling-aggregated.json' if aggregate else 'ev-scaling-profile.json')
records=[]
real_runpp=pp.runpp
for count in (128,500,4096,16384,65536):
    start=time.perf_counter()
    sessions=session_pool(fixture['blocks'],41001,count,synchronized=True)
    generation=time.perf_counter()-start
    for strategy in ('immediate','capacity_aware','mpc'):
        case=dict(strategy=strategy,aggregate_ev_nodes=aggregate,seed=41001,network_path=str(service.path('benchmark-suites',sid)/'network.json'),
                  blocks=fixture['blocks'],resolved_districts=fixture['districts'],limits=fixture['limits'],
                  network_capacity=fixture['network_capacity'],demand_measurement='supply_including_losses',stop_on_violation=False)
        sim=Simulator()
        start=time.perf_counter();sim.reset(case,fixture['demand']['normal'],sessions);reset=time.perf_counter()-start
        # All vehicles arrive at 18:00, untouched battery requests: matched stress snapshot.
        sim.index=72
        ctl=create_controller('mpc') if strategy=='mpc' else None
        pf=[0.,0]
        def timed(*args,**kwargs):
            start=time.perf_counter()
            try:return real_runpp(*args,**kwargs)
            finally:pf[0]+=time.perf_counter()-start;pf[1]+=1
        start=time.perf_counter()
        actions=ctl.actions(sim) if ctl else None
        decision=time.perf_counter()-start
        start=time.perf_counter()
        with patch.object(pp,'runpp',side_effect=timed):
            _,interval,_=sim.step(actions)
        step=time.perf_counter()-start
        row=dict(cars=count,strategy=strategy,generation_seconds=generation,reset_seconds=reset,
                 controller_seconds=decision,step_seconds=step,powerflow_seconds=pf[0],powerflow_calls=pf[1],
                 step_other_seconds=step-pf[0],buses=len(sim.net.bus),loads=len(sim.net.load),
                 controlled_groups=len(sim.sessions),aggregate_ev_nodes=aggregate,converged=interval['converged'],controller=ctl.last if ctl else None)
        records.append(row)
        output.write_text(json.dumps(dict(scope='Single synchronized 18:00 snapshot per fleet/strategy; concurrent benchmark active; reset includes cold/warm loss reconciliation; not full-day performance or capacity evidence',suite_id=sid,rows=records),indent=2),encoding='utf-8')
        print(json.dumps(row),flush=True)
