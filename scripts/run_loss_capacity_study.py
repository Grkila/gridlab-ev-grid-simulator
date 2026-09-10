"""Run and retain a fresh loss-aware capacity study through the actual MCP API."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import Client, StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]


async def main(args):
    output=ROOT/'artifacts/playground'/(args.output_name or 'aggregated-doubling-study' if args.aggregate_ev_nodes else 'uncapped-doubling-study' if args.until_failure else 'doubling-capacity-study' if args.search_mode=='doubling' else 'regulated-capacity-study' if args.mode=='regulated' else 'loss-capacity-study')
    output.mkdir(parents=True,exist_ok=True)
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/run_playground_mcp.py')],
                                cwd=str(ROOT),env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
    async with Client(params) as client:
        async def call(name,arguments):
            result=await client.call_tool(name,arguments)
            if result.is_error: raise RuntimeError(result.content)
            return result.structured_content
        await call('ev_get_contract',{'client_version':'1.0.0'})
        if args.job:
            job_id=args.job
        else:
            suite=await call('ev_create_benchmark',{'definition':dict(name='Voltage-regulated grid' if args.mode=='regulated' else 'Loss-inclusive consumption · corrected feeder model',
                operating_mode=args.mode,search_mode=args.search_mode,until_failure=args.until_failure,aggregate_ev_nodes=args.aggregate_ev_nodes,standard_fleet=args.reference,max_fleet=args.max_fleet,seeds=[41001])})
            (output/'suite.json').write_text(json.dumps(suite,indent=2),encoding='utf-8')
            job=await call('ev_start_benchmark',{'suite_id':suite['suite_id'],'config':dict(
                strategies=args.strategies,max_runtime_seconds=14400,case_runtime_seconds=240)})
            job_id=job['job_id']
            (output/'job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
            print(json.dumps(dict(job_id=job_id,suite_id=suite['suite_id'])),flush=True)
        while True:
            data=await call('ev_get_benchmark',{'job_id':job_id})
            (output/'results.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
            state=data['job']
            print(json.dumps({k:state.get(k) for k in ('job_id','status','current_test','current_strategy','current_fleet','current_step','completed_rows','elapsed_seconds','error')}),flush=True)
            if state['status'] not in ('starting','running'): break
            await asyncio.sleep(30)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--max-fleet',type=int,default=50000)
    parser.add_argument('--reference',type=int,default=100)
    parser.add_argument('--mode',choices=['as_supplied','regulated'],default='as_supplied')
    parser.add_argument('--strategies',nargs='+',default=['immediate','capacity_aware','mpc'])
    parser.add_argument('--job')
    parser.add_argument('--search-mode',choices=['refined','doubling'],default='refined')
    parser.add_argument('--until-failure',action='store_true')
    parser.add_argument('--aggregate-ev-nodes',action='store_true')
    parser.add_argument('--output-name')
    asyncio.run(main(parser.parse_args()))
