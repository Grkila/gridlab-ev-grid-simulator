"""Prepare the authorized presentation run through the current stdio MCP contract."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable, args=[str(ROOT / 'scripts/run_playground_mcp.py')])) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            async def call(name, args):
                result = await session.call_tool(name, args)
                if result.is_error:
                    raise RuntimeError(str(result.content))
                return json.loads(next(c.text for c in result.content if c.type == 'text'))
            await call('ev_get_contract', {'client_version': '1.0.0'})
            catalog = await call('ev_get_catalog', {})
            definition = catalog['example']
            definition.update(name='DEMO · 10.000 EV · poređenje strategija', hypothesis='Charging schedules change peak and constraints at equal requested energy.', case_origin='llm', operating_mode='regulated', strategies=['immediate','fixed_delay','randomized_delay','capacity_aware'], seeds=[41001], stop_on_violation=False, stress_first=False, max_cases=4, max_runtime_seconds=1200)
            definition['demand'].update(month=6, monthly_energy=76965, days_per_month=30)
            definition['fleet'].update(fleet_size=10000, charging_profile='home_only', location_mix={'residential':1,'workplace':0,'public':0})
            definition['assumptions'].append('Presentation demo: synthetic June home-only sessions, individual sessions, fixed seed; not measured city capacity.')
            saved = await call('ev_save_experiment', {'definition':definition})
            output=ROOT/'artifacts/playground/evidence/presentation/demo-run.json'
            args={'experiment_id':saved['experiment_id']}
            if output.exists():
                previous=json.loads(output.read_text(encoding='utf-8'))
                if previous['experiment']['experiment_id']==saved['experiment_id'] and (ROOT/'artifacts/playground/runtime/runs'/previous['run']['run_id']/'manifest.json').exists():
                    args['resume_run_id']=previous['run']['run_id']
            run = await call('ev_start_run', args)
            output.write_text(json.dumps({'experiment':saved,'run':run},indent=2,ensure_ascii=False),encoding='utf-8')
            print(json.dumps(run),flush=True)
            while run['status'] in ('starting','running','queued'):
                await asyncio.sleep(10)
                run=await call('ev_get_run',{'run_id':run['run_id']})
                output.write_text(json.dumps({'experiment':saved,'run':run},indent=2,ensure_ascii=False),encoding='utf-8')
                print(json.dumps({k:run.get(k) for k in ('run_id','status','completed_cases')}),flush=True)

if __name__ == '__main__':
    asyncio.run(main())



