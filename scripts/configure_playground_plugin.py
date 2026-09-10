"""Write portable plugin source's local MCP launcher for this checkout/interpreter."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mvgrid.paths import REPOSITORY_ROOT

if __name__ == "__main__":
    path = REPOSITORY_ROOT / "plugins/ev-hypothesis-playground/.mcp.json"
    config = {"mcpServers":{"ev-playground":{"command":sys.executable,"args":[str(REPOSITORY_ROOT/"scripts/run_playground_mcp.py")],"startup_timeout_sec":30,"tool_timeout_sec":120}}}
    path.write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
    print(path)
