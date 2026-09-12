"""Check Windows setup failures and exclusive port binding without running experiments."""
from pathlib import Path
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mvgrid.novi_sad.playground_app.server import create_server

assert os.name == 'nt', 'Run this check on Windows.'
shell = str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
checks = []

def rejected(script, arguments, expected, env=None):
    result = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), *arguments],
                            cwd=ROOT.parent, env=env, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert expected in output, output
    checks.append({'check': expected, 'exit_code': result.returncode})

with tempfile.TemporaryDirectory(prefix='windows handoff ') as folder:
    temp = Path(folder)
    scripts = temp / 'scripts'
    scripts.mkdir()
    for name in ('start.ps1', 'setup.ps1'):
        shutil.copy2(ROOT / 'scripts' / name, scripts / name)
    rejected(scripts / 'start.ps1', [], 'Setup is incomplete')
    rejected(scripts / 'setup.ps1', ['-PythonPath', str(temp / 'missing python.exe')], 'does not exist')
    env = os.environ.copy()
    env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
    rejected(scripts / 'setup.ps1', [], 'node.exe', env)

    server = create_server(0, temp / 'runtime')
    try:
        rejected(ROOT / 'scripts/start.ps1', ['-Port', str(server.server_port), '-NoBrowser'], 'is occupied')
        # The original socket still accepts connections after the rejected start.
        with socket.create_connection(server.server_address, timeout=3):
            pass
        checks.append({'check': 'Occupied-port owner remains available', 'passed': True})
        try:
            second = create_server(server.server_port, temp / 'runtime-second')
        except OSError:
            checks.append({'check': 'Two application servers cannot share a port', 'passed': True})
        else:
            second.server_close()
            raise AssertionError('The second server acquired an occupied port.')
    finally:
        server.server_close()

out = ROOT / 'artifacts/handoff/windows-launch.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'passed': True, 'checks': checks}, indent=2) + '\n', encoding='utf-8')
print(out.read_text(encoding='utf-8'))
