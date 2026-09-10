"""Validate and save a clean, explicitly loss-inclusive test set through MCP."""
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import Client, StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]


async def main():
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/run_playground_mcp.py')],
        cwd=str(ROOT),env={**os.environ,'PYTHONPATH':str(ROOT/'src')})
    records=[]
    async with Client(params) as client:
        for name,month,energy,days,scenario,fleets in [
            ('01 · Loss-aware summer baseline',6,76000,30,'base',[0,500]),
            ('02 · Loss-aware winter baseline',1,120000,31,'base',[0,500]),
            ('03 · Loss-aware worst winter',1,120000,31,'worst_case',[0,500]),
            ('04 · Loss-aware worst summer',6,76000,30,'worst_case',[0,500]),
            ('05 · Loss-aware charging comparison',6,76000,30,'base',[500,2000])]:
            definition=dict(name=name.replace('Loss-aware','Voltage-regulated'),operating_mode='regulated',hypothesis='Serve positive fleets under voltage regulation and energy-preserving baseline shifting; supplied consumption includes modeled network losses exactly once.',
                case_origin='llm',assumptions=['User clarified consumption includes losses on 2026-09-10.',
                'Seasonal demand amounts remain the existing 120000/76000 MWh presets; not newly transcribed from the low-resolution table.',
                'Synthetic corrected worst-path MV reduction; downstream share remains the explicit 0.5 assumption.',
                'Source voltage 1.04 pu and baseline demand shifted to a 220 MW peak while preserving daily energy.'],
                demand=dict(month=month,monthly_energy=energy,days_per_month=days,days=1,scenario=scenario,
                            measurement='supply_including_losses'),
                fleet=dict(fleet_size=100,energy_kwh=14,charger_kw=7.4,efficiency=.9,
                           location_mix=dict(residential=1,workplace=0,public=0)),
                fleet_sizes=fleets,strategies=['immediate','capacity_aware','mpc'],seeds=[41001],
                stop_on_violation=False,stress_first=False,max_cases=6,max_runtime_seconds=900,
                assertions=[dict(type='hard',metric=metric,operator=op,value=value) for metric,op,value in [
                    ('min_voltage_pu','ge',.95),('max_line_loading_percent','le',100),
                    ('max_transformer_loading_percent','le',100),('max_network_capacity_loading_percent','le',100),
                    ('max_district_loading_percent','le',100),('unmet_energy_kwh','le',1e-5),('nonconverged_steps','le',0)]])
            valid=await client.call_tool('ev_validate_experiment',{'definition':definition})
            if valid.is_error: raise RuntimeError(valid.content)
            saved=await client.call_tool('ev_save_experiment',{'definition':definition})
            if saved.is_error: raise RuntimeError(saved.content)
            record=dict(name=definition['name'],experiment_id=saved.structured_content['experiment_id'])
            records.append(record); print(json.dumps(record),flush=True)
    (ROOT/'artifacts/playground/loss-test-experiments.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


if __name__=='__main__': asyncio.run(main())
