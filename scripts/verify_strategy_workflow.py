"""Real stdio MCP workflow and full-horizon four-controller proof of concept."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mcp import Client, StdioServerParameters
from mvgrid.paths import REPOSITORY_ROOT


async def verify():
    root=REPOSITORY_ROOT/'artifacts/playground/strategy-poc-runtime'
    params=StdioServerParameters(command=sys.executable,args=[str(REPOSITORY_ROOT/'scripts/run_playground_mcp.py')],
        env={**os.environ,'EV_PLAYGROUND_HOME':str(root),'EV_PLAYGROUND_BROKER_URL':'','PYTHONPATH':str(REPOSITORY_ROOT/'src')},cwd=tempfile.gettempdir())
    async with Client(params) as client:
        async def call(name,**kwargs):
            result=await client.call_tool(name,kwargs)
            assert not result.is_error,(name,result.content)
            return result.structured_content
        catalog=await call('ev_get_strategy_catalog')
        assert len(catalog['strategies'])==9
        proposed=await call('ev_strategy_command',command='STRATEGY PROPOSE\nname: proof_of_concept\nidea: Exercise strategy development and comparison.\nobjective: Verify a reproducible implementation workflow.\nresearch: new_hypothesis')
        specified=await call('ev_strategy_command',command=dict(command='SPECIFY',based_on=proposed['record_id'],information=['current sessions'],constraints=['charger and grid limits'],algorithm='Allocate headroom according to charging slack.',fallback='Zero charge if observations unavailable.'))
        build=await call('ev_strategy_command',command=dict(command='BUILD',based_on=specified['record_id']))
        assert build['status']=='implementation_required' and 'coding_prompt' in build
        assert (await call('ev_get_strategy_record',record_id=specified['record_id']))==specified
        invalid=await client.call_tool('ev_strategy_command',{'command':'STRATEGY BUILD\nbased_on: ../../outside'})
        assert invalid.is_error
        base=await call('ev_save_experiment',definition=dict(name='Strategy workflow proof of concept',hypothesis='All new controllers execute full episodes with auditable energy accounting.',strategies=['capacity_aware'],fleet={'fleet_size':8},demand={'monthly_energy':60000},stress_first=False,max_runtime_seconds=300,assertions=[dict(type='hard',metric='nonconverged_steps',operator='le',value=0)]))
        prepared=await call('ev_strategy_command',command=dict(command='COMPARE',scenario=base['experiment_id'],candidates=['capacity_aware','least_laxity_first','valley_filling','mpc','voltage_responsive'],seeds=[11],max_cases=5,max_runtime_seconds=300))
        experiment=prepared['experiments'][0]
        run=await call('ev_start_run',experiment_id=experiment['experiment_id'])
        deadline=time.monotonic()+330
        while True:
            state=await call('ev_get_run',run_id=run['run_id'])
            if state['status'] not in ('starting','running'): break
            assert time.monotonic()<deadline,'Run timeout'
            await asyncio.sleep(1)
        assert state['status']=='completed',state
        results=await call('ev_get_results',run_id=run['run_id'])
        assert len(results['cases'])==5
        summary=[]
        for case in results['cases']:
            m=case['metrics']
            assert case['complete'] and m['nonconverged_steps']==0
            assert m['delivered_energy_kwh']<=m['requested_energy_kwh']+1e-6
            assert abs(m['delivered_energy_kwh']+m['unmet_energy_kwh']-m['requested_energy_kwh'])<1e-5
            summary.append(dict(strategy=case['strategy'],metrics=m))
        evidence=dict(status='passed',scope='Workflow/protocol and full-horizon execution; no claim of superior controller performance.',run_id=run['run_id'],experiment_id=experiment['experiment_id'],runtime_root=str(root),records=[proposed['record_id'],specified['record_id'],build['record_id']],cases=summary)
        out=REPOSITORY_ROOT/'artifacts/playground/evidence/strategy_workflow.json'
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(evidence,indent=2))


if __name__=='__main__': asyncio.run(verify())
