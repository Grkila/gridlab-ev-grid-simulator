"""Explicit live acceptance: Codex CLI must call real MCP tools, not simulated events."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground_app.chat import ChatService
from mvgrid.novi_sad.playground.service import Service, write_json

if __name__=='__main__':
    import threading
    from mvgrid.novi_sad.playground_app.server import create_server
    server=create_server(0)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    chat=server.chat_service
    result=chat.start('Use ev_playground MCP tools to validate and save an example called Active district comparison. Hypothesis: capacity-aware charging reduces electrical violations while exposing energy shortfalls. Use fleet_size 250, strategies immediate and capacity_aware, seeds [1], stop_on_violation false explicitly so both full trajectories are recorded, stress_first false, max_runtime_seconds 180. Leave default demand and limits. Then start this saved experiment. Report the returned experiment ID and run ID. Do not wait or poll for completion; the GUI will monitor it. Do not claim any result before the run completes.')
    while result['status']=='running':
        time.sleep(.5)
        result=chat.get(result['chat_id'])
    calls=[e['item'] for e in result['events'] if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
    names=[c.get('tool') for c in calls]
    evidence={'status':result['status'],'chat_id':result['chat_id'],'tools':names,'tool_statuses':[c.get('status') for c in calls],'messages':result['messages'],'error':result.get('error'),'implementation':'native codex exec --json plus real local stdio MCP'}
    starts=[c for c in calls if c.get('tool')=='ev_start_run' and c.get('result')]
    if starts:
        run=starts[-1]['result'].get('structured_content',{})
        if not run:
            run=json.loads(starts[-1]['result']['content'][0]['text'])
        deadline=time.monotonic()+180
        while run['status'] in ('starting','running') and time.monotonic()<deadline:
            time.sleep(.5)
            run=Service().get_run(run['run_id'])
        evidence['worker_after_cli_exit']={'run_id':run['run_id'],'status':run['status'],'completed_cases':run.get('completed_cases')}
    server.shutdown()
    server.server_close()
    write_json(REPOSITORY_ROOT/'artifacts/playground/evidence/codex_chat.json',evidence)
    print(json.dumps(evidence,indent=2))
    assert result['status']=='completed', result.get('error')
    assert {'ev_validate_experiment','ev_save_experiment','ev_start_run'}.issubset(names), names
    assert all(c.get('status')=='completed' and not c.get('error') for c in calls)

    assert evidence["worker_after_cli_exit"]["status"]=="completed", evidence
