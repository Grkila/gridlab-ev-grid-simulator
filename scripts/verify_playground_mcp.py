"""End-to-end stdio verification using the actual MCP client/server protocol."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mcp import Client, StdioServerParameters
from mvgrid.paths import REPOSITORY_ROOT


async def verify(root: str) -> dict:
    root = str(Path(root).resolve())
    params = StdioServerParameters(command=sys.executable, args=[str(REPOSITORY_ROOT / "scripts" / "run_playground_mcp.py")],
        env={**os.environ, "EV_PLAYGROUND_HOME":root, "PYTHONPATH":str(REPOSITORY_ROOT / "src")}, cwd=tempfile.gettempdir())
    async with Client(params) as client:
        tools = await client.list_tools()
        assert len(tools.tools) >= 10
        async def call(name, **args):
            result = await client.call_tool(name, args)
            if result.is_error:
                raise AssertionError(f"{name}: {result.content}")
            return result.structured_content
        catalog = await call("ev_get_catalog")
        assert len(catalog["districts"]) == 10
        definition = catalog["example"]
        definition.update(name="MCP protocol acceptance",strategies=["immediate","capacity_aware"],stress_first=False,stop_on_violation=False,
                          assertions=[{"type":"hard","metric":"nonconverged_steps","operator":"le","value":0}])
        definition["fleet"]["fleet_size"] = 8
        validation = await call("ev_validate_experiment",definition=definition)
        assert validation["estimated_power_flows"] == 264
        invalid = await client.call_tool("ev_validate_experiment",{"definition":{**definition,"unexpected":True}})
        assert invalid.is_error
        saved = await call("ev_save_experiment",definition=definition)
        duplicate = await call("ev_save_experiment",definition=definition)
        assert saved["experiment_id"] == duplicate["experiment_id"]
        fetched = await call('ev_get_experiment', experiment_id=saved['experiment_id'])
        assert {k:v for k,v in fetched.items() if k!='contract'} == {k:v for k,v in saved.items() if k!='contract'}
        listing = await call('ev_list_experiments', limit=1)
        assert listing['experiments'][0]['experiment_id'] == saved['experiment_id']
        assert 'definition' not in listing['experiments'][0]

        run = await call("ev_start_run",experiment_id=saved["experiment_id"])
        await call("ev_cancel_run",run_id=run["run_id"])
        async def wait(run_id):
            deadline = time.monotonic()+180
            while time.monotonic()<deadline:
                state = await call("ev_get_run",run_id=run_id)
                if state["status"] not in ("running","starting"):
                    return state
                await asyncio.sleep(.25)
            raise AssertionError("MCP job timed out")
        cancelled = await wait(run["run_id"])
        assert cancelled["status"] == "cancelled", cancelled
        # Resume through a freshly connected client below, exercising persistent jobs.
    async with Client(params) as client:
        async def call(name, **args):
            result = await client.call_tool(name,args)
            assert not result.is_error, result.content
            return result.structured_content
        async def wait(run_id):
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                state=await call("ev_get_run",run_id=run_id)
                if state["status"] not in ("running","starting"): return state
                await asyncio.sleep(.25)
            raise AssertionError("resumed job timed out")
        await call("ev_start_run",experiment_id=saved["experiment_id"],resume_run_id=run["run_id"])
        completed=await wait(run["run_id"])
        assert completed["status"]=="completed" and completed["verdict"]=="passed",completed
        results=await call("ev_get_results",run_id=run["run_id"])
        assert len(results["cases"])==2 and "intervals" not in results["cases"][0]
        first_page=await call('ev_get_results',run_id=run['run_id'],limit=1)
        second_page=await call('ev_get_results',run_id=run['run_id'],limit=1,after=first_page['next_cursor'])
        assert first_page['cases']+second_page['cases']==results['cases']
        assert first_page['evaluation']==results['evaluation'] and first_page['evaluation_scope']=='whole_run'
        assert second_page['next_cursor'] is None

        detail=await call("ev_get_results",run_id=run["run_id"],case_id=results["cases"][0]["case_id"],include_intervals=True)
        assert len(detail["cases"][0]["intervals"])>=96
        assert detail["cases"][0]["metrics"]["pending_energy_kwh"] < 1e-6
        revised=await call("ev_add_cases",experiment_id=saved["experiment_id"],patch={"seeds":[2],"strategies":["immediate"]})
        assert revised["experiment_id"] != saved["experiment_id"]
        second=await call("ev_start_run",experiment_id=revised["experiment_id"])
        assert (await wait(second["run_id"]))["status"]=="completed"
        comparison=await call("ev_compare_runs",run_ids=[run["run_id"],second["run_id"]])
        assert "seeds" in comparison["differing_fields"] and not comparison["paired_compatible"]
        district_definition = {
            **definition,
            "name": "MCP district capacity counterexample",
            "strategies": ["immediate"],
            "stop_on_violation": True,
            "fleet": {**definition["fleet"], "district_mix": {"NS5": 1.0}},
            "district_capacity": {
                "scenario": "central",
                "overrides": {"NS5": {"capacity_kw": 1.0, "provenance": "Deliberately low synthetic acceptance limit"}},
            },
            "assertions": [{"type": "hard", "metric": "district_overload_steps", "operator": "le", "value": 0}],
        }
        district_saved = await call("ev_save_experiment", definition=district_definition)
        district_run = await call("ev_start_run", experiment_id=district_saved["experiment_id"])
        district_state = await wait(district_run["run_id"])
        assert district_state["status"] == "stopped_on_violation" and district_state["verdict"] == "incomplete", district_state
        district_result = await call("ev_get_results", run_id=district_run["run_id"], case_id="case-0000", include_intervals=True)
        district_case = district_result["cases"][0]
        assert district_case["metrics"]["district_overload_steps"] == 1
        assert len(district_case["intervals"]) == 1
        assert any(v["kind"] == "district_capacity_exceeded" for v in district_case["intervals"][0]["violations"])
        assert all(s["district_id"] == "NS5" for s in district_case["sessions"])
        district_comparison = await call("ev_compare_runs", run_ids=[run["run_id"], district_run["run_id"]])
        assert not district_comparison["paired_compatible"] and "district_capacity" in district_comparison["differing_fields"]
        # Terminal state is persisted just before process exit; release Windows log handles before temp cleanup.
        import psutil
        for run_id in (run['run_id'], second['run_id'], district_run['run_id']):
            state=await call('ev_get_run', run_id=run_id)
            try:
                await asyncio.to_thread(psutil.Process(state['pid']).wait, timeout=10)
            except psutil.NoSuchProcess:
                pass
        return {"passed":True,"transport":"stdio","tool_count":len(tools.tools),"checks":["discovery","typed validation","invalid input","immutable save","background run","cancellation","server restart","resume","results","interval detail","revision","comparison","district capacity counterexample","district car placement","capacity comparison boundary"],"runs":[run["run_id"],second["run_id"],district_run["run_id"]]}


if __name__=="__main__":
    if len(sys.argv)>1:
        print(json.dumps(asyncio.run(verify(sys.argv[1])),indent=2))
    else:
        with tempfile.TemporaryDirectory() as root:
            print(json.dumps(asyncio.run(verify(root)),indent=2))
