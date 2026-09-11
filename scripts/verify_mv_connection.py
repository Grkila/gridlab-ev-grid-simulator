"""Matched MCP sensitivity runs; bypassing legacy LV budgets is not a new substation design."""
import asyncio
import copy
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/playground/mv-connection-study'

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    async with stdio_client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/run_playground_mcp.py')])) as (rd,wr):
        async with ClientSession(rd,wr) as session:
            await session.initialize()
            async def call(name,args):
                result=await session.call_tool(name,args)
                if result.is_error:raise RuntimeError(str(result.content))
                return json.loads(next(c.text for c in result.content if c.type=='text'))
            await call('ev_get_contract',{'client_version':'1.0.0'})
            catalog=await call('ev_get_catalog',{})
            results=[]
            for location in ['residential','workplace']:
                for share in [1.,0.]:
                    key=f'{location}-lv{int(share)}'
                    target=OUT/f'{key}.json'
                    if target.exists():
                        saved=json.loads(target.read_text())
                        if saved.get('run',{}).get('status')=='completed':
                            results.append(saved);continue
                    definition=copy.deepcopy(catalog['example'])
                    definition.update(name=f'SN sensitivity / {key} / 20000 EV',hypothesis='Removing EV share from existing LV aggregate budgets may improve feasibility; timing and connection are separate factors.',case_origin='llm',strategies=['immediate'],seeds=[62001],stop_on_violation=False,stress_first=False,max_cases=1,max_runtime_seconds=600,operating_mode='as_supplied')
                    definition['demand'].update(month=6,monthly_energy=76965,days_per_month=30,days=1)
                    definition['fleet'].update(fleet_size=20000,energy_kwh=14,charger_kw=7.4,efficiency=.9,charging_profile='whole_day',location_mix={k:float(k==location) for k in ['residential','workplace','public']})
                    definition['network_capacity'].update(lv_baseline_fraction=.5,lv_ev_fraction=share)
                    definition['assertions']=[dict(type='hard',metric=m,operator='le',value=0) for m in ['unmet_energy_kwh','nonconverged_steps','overload_steps','district_overload_steps','network_capacity_overload_steps','energy_limit_exceeded_steps']]
                    definition['assertions'].append(dict(type='hard',metric='min_voltage_pu',operator='ge',value=.95))
                    definition['assumptions'] += ['14 battery kWh per vehicle, not a full 60-kWh battery.','lv_ev_fraction=0 is idealized bypass of existing aggregate LV and downstream transformer budgets. No physical new transformer, connector losses, ratings or cost is modeled. Upstream AC network and limits remain unchanged.','Same seed and location profile within each connection pair; location/time pairs are analyzed separately.']
                    experiment=await call('ev_save_experiment',{'definition':definition})
                    run=await call('ev_start_run',{'experiment_id':experiment['experiment_id']})
                    record=dict(key=key,experiment=experiment,run=run)
                    target.write_text(json.dumps(record,indent=2),encoding='utf-8')
                    print(json.dumps(dict(key=key,run_id=run['run_id'],status=run['status'])),flush=True)
                    while run['status'] in ['starting','running','queued']:
                        await asyncio.sleep(5)
                        run=await call('ev_get_run',{'run_id':run['run_id']})
                    record['run']=run
                    record['results']=await call('ev_get_results',{'run_id':run['run_id'],'limit':20})
                    target.write_text(json.dumps(record,indent=2),encoding='utf-8')
                    results.append(record)
                    print(json.dumps(dict(key=key,status=run['status'],verdict=run.get('verdict'))),flush=True)
            (OUT/'index.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

if __name__=='__main__':asyncio.run(main())
