"""Read-only acceptance of benchmark tools through a fresh stdio MCP server."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


async def main():
    with tempfile.TemporaryDirectory(prefix='benchmark-mcp-') as runtime:
        params = StdioServerParameters(command=sys.executable,
            args=[str(ROOT/'scripts/run_playground_mcp.py')], cwd=str(ROOT),
            env={**os.environ, 'EV_PLAYGROUND_HOME': runtime, 'PYTHONPATH': str(ROOT/'src')})
        async with Client(params) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            expected = {'ev_get_benchmark_catalog', 'ev_create_benchmark', 'ev_start_benchmark',
                        'ev_get_benchmark', 'ev_cancel_benchmark', 'ev_compare_benchmark'}
            assert expected <= names, expected-names
            result = await client.call_tool('ev_get_benchmark_catalog', {})
            assert not result.is_error, result.content
            assert len(result.structured_content['tests']) == 10
            print(json.dumps({'status': 'passed', 'tools': sorted(expected), 'tests': 10}))


if __name__ == '__main__':
    asyncio.run(main())
