"""Generate or check plugin instructions and version pin from the project contract."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mvgrid.novi_sad.playground.agent_contract import VERSION, get_contract, plugin_skill


def sync(plugin, check=False):
    plugin = Path(plugin)
    config_path = plugin / '.mcp.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['mcpServers']['ev-playground'].setdefault('env', {})['EV_AGENT_CONTRACT_VERSION'] = VERSION
    generated = {
        plugin / 'skills/ev-experiments/SKILL.md': plugin_skill(),
        plugin / 'assets/agent-contract.json': json.dumps(get_contract(), indent=2) + '\n',
        config_path: json.dumps(config, indent=2) + '\n',
    }
    for path, content in generated.items():
        if check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                raise ValueError(f'Generated contract drift: {path}. Run scripts/sync_agent_contract.py.')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    return VERSION


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', default=str(ROOT / 'plugins/ev-hypothesis-playground'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(sync(args.plugin, args.check))
