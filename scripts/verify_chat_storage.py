"""Reproducible payload/read measurement using synthetic evidence, without Codex."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.service import Service,read_json,write_json
from mvgrid.novi_sad.playground_app.chat import ChatService


def verify():
    with tempfile.TemporaryDirectory() as root:
        service=Service(root);folder=service._path('runs','run-size')
        write_json(folder/'state.json',dict(run_id='run-size',status='completed'))
        case=dict(case_id='case-0000',metrics={'peak_demand_kw':42},complete=True,intervals=[{'payload':'x'*1000000}])
        write_json(folder/'cases'/'case-0000.json',case)
        full=service.get_results('run-size');compact=service.get_results('run-size',summary=True)
        read_details=[]
        def counted(path):
            if path.parent.name=='cases':read_details.append(str(path))
            return read_json(path)
        with patch('mvgrid.novi_sad.playground.service.read_json',side_effect=counted):
            assert service.get_results('run-size',summary=True)==compact
        assert not read_details
        chat=ChatService(service)
        record=dict(chat_id='chat-size',status='completed',messages=[],events=[],sequence=0,transport_version=1)
        chat._event(record,dict(type='item.completed',item=dict(type='mcp_tool_call',result=full)))
        write_json(chat.path('chat-size'),record)
        initial=chat.snapshot('chat-size');delta=chat.snapshot('chat-size',initial['cursor'])
        output_id=initial['events'][0]['full_url'].split('/')[-1]
        assert chat.output('chat-size',output_id)['item']['result']==full
        assert delta['events']==[] and delta['messages']==[]
        size=lambda value:len(json.dumps(value).encode())
        return dict(fixture='Synthetic 1 MB tool result; not a simulation benchmark',
                    full_result_bytes=size(full),summary_result_bytes=size(compact),warm_summary_detail_reads=len(read_details),
                    initial_chat_bytes=size(initial),unchanged_chat_delta_bytes=size(delta),full_evidence_retrievable=True)


if __name__=='__main__':
    result=verify()
    write_json(REPOSITORY_ROOT/'artifacts/playground/evidence/chat-storage-check.json',result)
    print(json.dumps(result,indent=2))
