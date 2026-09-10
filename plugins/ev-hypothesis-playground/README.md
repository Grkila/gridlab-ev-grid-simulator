# EV Hypothesis Playground

This Codex plugin teaches an agent to turn EV-charging questions into bounded, reproducible experiments on the Novi Sad reduced-grid planning proxy. Its local MCP tools validate and freeze experiment definitions, run or resume cases, expose progress and results, and compare charging strategies.

The plugin is designed for automatic invocation when a request concerns EV hypothesis experiments. It keeps model assumptions, metric boundaries, seeds, and implementation fingerprints visible, and treats failed cases as counterexamples rather than silently changing the hypothesis.

The MCP server runs on the local machine and requires the Schneider challenge checkout and its `.venv`. The plugin's `.mcp.json` points Codex to that local backend. After cloning or moving the checkout, run `python scripts/setup_playground_plugin.py` from the project (or invoke that script by absolute path from any directory). It resolves the checkout, verifies MCP imports in `.venv`, and regenerates the native interpreter and launcher paths. Use `--python <native-python-path>` for a different environment or `--output <path>` to prepare another configuration. Restart the MCP connection after regenerating its configuration.

