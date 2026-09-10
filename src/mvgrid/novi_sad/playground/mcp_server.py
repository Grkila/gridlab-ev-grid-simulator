"""Local typed MCP interface; tools orchestrate experiments, never arbitrary code."""
from __future__ import annotations
from typing import Any, Annotated, get_type_hints
import inspect
import json
import os
from pydantic import BaseModel, Field, ValidationError, create_model
from .agent_contract import get_contract, render_instructions, check_version, stamp, ErrorDetail, ToolResult
from .tool_contracts import RESULT_TYPES
from .schema import Experiment, TrainingConfig, StrictModel
from .benchmark import BenchmarkConfig, BenchmarkRunConfig
from .scenario_workflow import ScenarioWorkflow, ScenarioConditions, ExperimentChoices
from .strategy_contract import StrategyContract, StrategyProposal, AlgorithmSpecification
from .strategy_workflow import StrategyCommand
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from .service import Service
from functools import wraps
from mcp.server.mcpserver.exceptions import ToolError

ExperimentPatch=create_model('ExperimentPatch',__base__=StrictModel,**{name:(field.annotation | None,None) for name,field in Experiment.model_fields.items()})

def tool_errors(fn):
    output_type=RESULT_TYPES.get(fn.__name__,ToolResult)
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            # SDK validates typed models; services retain their mapping API.
            args=tuple(a.model_dump(mode='json',exclude_unset=True) if isinstance(a,BaseModel) else a for a in args)
            kwargs={k:v.model_dump(mode='json',exclude_unset=True) if isinstance(v,BaseModel) else v for k,v in kwargs.items()}
            result=fn(*args, **kwargs)
            return output_type.model_validate(stamp(fn.__name__,result)).model_dump(mode='json',exclude_unset=True)
        except (ValueError, FileNotFoundError, KeyError) as error:
            code='not_found' if isinstance(error,FileNotFoundError) else 'contract_mismatch' if 'Contract mismatch' in str(error) else 'invalid_input'
            fields=['.'.join(map(str,e['loc'])) for e in error.errors()] if isinstance(error,ValidationError) else []
            detail=ErrorDetail(code=code,message=str(error),fields=fields,
                next_action='Inspect ev_get_contract and the relevant live catalog; correct the named input or use a returned ID.')
            raise ToolError(detail.model_dump_json()) from error
    wrapped.__annotations__={**get_type_hints(fn,include_extras=True),'return':output_type}
    wrapped.__signature__=inspect.signature(fn,eval_str=True).replace(return_annotation=output_type)
    return wrapped

server = MCPServer("ev_playground_mcp", instructions=render_instructions())
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_catalog() -> dict[str, Any]:
    """Discover experiment JSON schema, supported strategies, metrics and a valid example."""
    return Service().catalog()

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_list_experiments(limit: Annotated[int, Field(ge=1,le=100)] = 20, after: str | None = None) -> dict[str, Any]:
    """Page compact experiment/run records in ID order; pass next_cursor as after until null."""
    return Service().list_page(limit,after)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_experiment(experiment_id: str) -> dict[str, Any]:
    """Retrieve one complete immutable experiment definition by its returned ID."""
    return Service().get_experiment(experiment_id)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_validate_experiment(definition: Experiment) -> dict[str, Any]:
    """Validate typed JSON and expand a bounded case matrix without executing it."""
    return Service().validate_experiment(definition)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_save_experiment(definition: Experiment) -> dict[str, Any]:
    """Save a validated immutable definition; identical definitions reuse the same ID."""
    return Service().save_experiment(definition)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_add_cases(experiment_id: str, patch: ExperimentPatch) -> dict[str, Any]:
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
def ev_get_results(run_id: str, case_id: str | None = None, include_intervals: bool = False, limit: Annotated[int, Field(ge=1,le=100)] = 20, after: str | None = None) -> dict[str, Any]:
    """Page case summaries using next_cursor/after. Evaluation always covers the whole run. Full detail requires case_id."""
    if include_intervals and not case_id:
        raise ValueError("Provide case_id when requesting detailed interval data.")
    return Service().get_results(run_id,case_id,summary=not include_intervals,limit=limit,after=after)


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
def ev_train_rl(experiment_id: str, config: TrainingConfig) -> dict[str, Any]:
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


@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_benchmark_catalog() -> dict[str, Any]:
    """List the ten standard fixtures, saved suites, algorithms and benchmark jobs."""
    from .benchmark import BenchmarkService
    return BenchmarkService().catalog()


@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_create_benchmark(definition: BenchmarkConfig) -> dict[str, Any]:
    """Validate and freeze ten tests, network, nested vehicle pools and evaluation seeds."""
    from .benchmark import BenchmarkService
    return BenchmarkService().create_suite(definition)


@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_start_benchmark(suite_id: str, config: BenchmarkRunConfig) -> dict[str, Any]:
    """Evaluate registered algorithms on frozen fixtures; capacity is a tested lower bound."""
    from .benchmark import BenchmarkService
    return BenchmarkService().start(suite_id, config)


@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_benchmark(job_id: str) -> dict[str, Any]:
    """Read benchmark progress, per-test metrics and all tested fleet outcomes."""
    from .benchmark import BenchmarkService
    return BenchmarkService().results(job_id)


@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_cancel_benchmark(job_id: str) -> dict[str, Any]:
    """Cancel a benchmark; incomplete cells never become passes."""
    from .benchmark import BenchmarkService
    return BenchmarkService().cancel(job_id)


@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_compare_benchmark(suite_id: str) -> dict[str, Any]:
    """Compare saved implementations only on the same immutable benchmark fixtures."""
    from .benchmark import BenchmarkService
    return BenchmarkService().comparison(suite_id)


@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_contract(client_version: str | None = None) -> dict[str,Any]:
    """Discover canonical rules/workflows and check plugin compatibility before mutation."""
    return get_contract(client_version)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_save_scenario(definition: ScenarioConditions, parent_id: str | None = None) -> dict[str,Any]:
    """Validate and freeze exogenous conditions; a revision reports changed fields and preserves its parent."""
    return ScenarioWorkflow().save(definition,parent_id)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_scenario(scenario_id: str) -> dict[str,Any]:
    """Read a frozen scenario's conditions, network reference and revision differences."""
    return ScenarioWorkflow().get(scenario_id)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_prepare_experiment(scenario_id: str, config: ExperimentChoices) -> dict[str,Any]:
    """Combine frozen conditions with algorithms/assertions/budgets. This saves but does not run."""
    return ScenarioWorkflow().prepare(scenario_id,config)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_propose_strategy(definition: StrategyProposal) -> dict[str,Any]:
    """Save an algorithm idea with an explicit research or engineering-baseline classification."""
    return StrategyContract().propose(definition)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_specify_strategy(record_id: str, definition: AlgorithmSpecification) -> dict[str,Any]:
    """Specify causal observations, forecasts, actions, constraints, fallback and planned repository checks."""
    return StrategyContract().specify(record_id,definition)

@server.tool(annotations=WRITE, structured_output=True)
@tool_errors
def ev_verify_strategy(record_id: str) -> dict[str,Any]:
    """Execute only the saved specification's named repository tests; bind checks to source/spec hashes. Not scientific validation."""
    return StrategyContract().verify(record_id)

@server.tool(annotations=READ, structured_output=True)
@tool_errors
def ev_get_strategy_verification(record_id: str) -> dict[str,Any]:
    """Read recorded repository checks and mark them stale if specification, source or tests changed."""
    return StrategyContract().get_verification(record_id)


def main():
    check_version(os.environ.get('EV_AGENT_CONTRACT_VERSION'))
    server.run(transport="stdio")

if __name__ == "__main__":
    main()




