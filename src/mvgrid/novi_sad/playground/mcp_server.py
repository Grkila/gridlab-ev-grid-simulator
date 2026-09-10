"""Local typed MCP interface; tools orchestrate experiments, never arbitrary code."""
from __future__ import annotations
from typing import Any
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from .service import Service
from functools import wraps
from mcp.server.mcpserver.exceptions import ToolError

def tool_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (ValueError, FileNotFoundError, KeyError) as error:
            raise ToolError(str(error)) from error
    return wrapped

server = MCPServer("ev_playground_mcp", instructions="Synthetic EV hypothesis playground. Validate and freeze experiments before running. Distinguish incomplete, rejected and completed evidence. Detailed network checks are optional.")
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_catalog() -> dict[str, Any]:
    """Discover experiment JSON schema, supported strategies, metrics and a valid example."""
    return Service().catalog()

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_list_experiments() -> dict[str, Any]:
    """List saved experiment revisions and local runs."""
    s = Service()
    return {"experiments": s.list_experiments(), "runs": s.list_runs()}

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_validate_experiment(definition: dict) -> dict[str, Any]:
    """Validate typed JSON and expand a bounded case matrix without executing it."""
    return Service().validate_experiment(definition)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_save_experiment(definition: dict) -> dict[str, Any]:
    """Save a validated immutable definition; identical definitions reuse the same ID."""
    return Service().save_experiment(definition)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_add_cases(experiment_id: str, patch: dict) -> dict[str, Any]:
    """Create a revision by replacing supplied top-level fields, including seeds or fleet_sizes."""
    return Service().add_cases(experiment_id, patch)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_start_run(experiment_id: str, resume_run_id: str | None = None) -> dict[str, Any]:
    """Start one background worker or resume a matching interrupted run; returns a run ID promptly."""
    return Service().start_run(experiment_id, resume_run_id)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_run(run_id: str) -> dict[str, Any]:
    """Get progress, coverage, verdict and actionable errors for a run."""
    return Service().get_run(run_id)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_cancel_run(run_id: str) -> dict[str, Any]:
    """Request cancellation at the next interval; completed cases remain resumable."""
    return Service().cancel_run(run_id)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_results(run_id: str, case_id: str | None = None, include_intervals: bool = False) -> dict[str, Any]:
    """Get metrics and assertion counterexamples; opt into detailed interval/block snapshots for one case."""
    if include_intervals and not case_id:
        raise ValueError("Provide case_id when requesting detailed interval data.")
    result = Service().get_results(run_id, case_id)
    if not include_intervals:
        result["cases"] = [{k:v for k,v in c.items() if k not in ("intervals", "sessions", "blocks", "hierarchy_nodes", "hierarchy_edges")} for c in result["cases"]]
    return result

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_compare_runs(run_ids: list[str]) -> dict[str, Any]:
    """Compare saved metrics and expose differences that prevent a controlled paired comparison."""
    return Service().compare_runs(run_ids)

from .strategy_workflow import register_strategy_tools
register_strategy_tools(server, READ, WRITE, tool_errors)


@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_rl_catalog() -> dict[str, Any]:
    """List trained immutable RL models, training jobs and default settings."""
    from .rl_service import RLService
    return RLService().catalog()


@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_train_rl(experiment_id: str, config: dict) -> dict[str, Any]:
    """Train a fresh binary policy on randomized days; returns a bounded background job."""
    from .rl_service import RLService
    return RLService().start(experiment_id, config)


@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_rl_job(job_id: str) -> dict[str, Any]:
    """Read training progress and measured episode history."""
    from .rl_service import RLService
    return RLService().get_job(job_id)


@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_cancel_rl(job_id: str) -> dict[str, Any]:
    """Request cancellation; incomplete training never publishes a selectable model."""
    from .rl_service import RLService
    return RLService().cancel(job_id)


def main():
    server.run(transport="stdio")

if __name__ == "__main__":
    main()




