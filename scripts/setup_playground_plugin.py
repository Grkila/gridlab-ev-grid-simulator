"""Regenerate machine-specific MCP paths after cloning or moving the checkout."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys


def configure(root, interpreter, output):
    root=Path(root).resolve(); interpreter=Path(interpreter).resolve(); output=Path(output).resolve()
    launcher=root/'scripts'/'run_playground_mcp.py'
    if not interpreter.is_file() or interpreter.suffix.lower() in ('.bat','.cmd'):
        raise ValueError('Choose the native Python executable in the project environment.')
    if not launcher.is_file(): raise ValueError('MCP launcher is missing from the checkout.')
    subprocess.run([str(interpreter),'-c','import mcp; from mvgrid.novi_sad.playground import mcp_server'],
                   env={**os.environ,'PYTHONPATH':str(root/'src')},cwd=str(root),check=True,timeout=60,
                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    sys.path.insert(0,str(root/'src'))
    from mvgrid.novi_sad.playground.agent_contract import VERSION
    config={'mcpServers':{'ev-playground':dict(command=interpreter.as_posix(),args=[launcher.as_posix()],
                                             startup_timeout_sec=30,tool_timeout_sec=120,
                                             env={'EV_AGENT_CONTRACT_VERSION': VERSION})}}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    return output


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',default=str(root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')))
    parser.add_argument('--output',default=str(root/'plugins/ev-hypothesis-playground/.mcp.json'))
    args=parser.parse_args()
    print(configure(root,args.python,args.output))
