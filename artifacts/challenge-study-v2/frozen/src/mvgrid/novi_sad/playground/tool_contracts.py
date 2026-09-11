"""Typed output surfaces; additive fields preserve legacy result payloads."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from .agent_contract import ToolResult
from .schema import Experiment
from .scenario_workflow import ScenarioConditions
from .benchmark import BenchmarkConfig, BenchmarkRunConfig
from .continuous_campaign import CampaignConfig


class OpenRecord(BaseModel):
    model_config=ConfigDict(extra='allow')


class CaseIdentity(OpenRecord):
    case_id: str
    strategy: str
    seed: int
    fleet_size: int


class CaseResult(CaseIdentity):
    metrics: dict[str,float | int | None]
    complete: bool = True


class RunRecord(OpenRecord):
    run_id: str
    status: str
    experiment_id: str | None = None
    verdict: str | None = None


class ExperimentResult(ToolResult):
    experiment_id: str
    definition: Experiment


class ValidationResult(ToolResult):
    definition: Experiment
    cases: list[CaseIdentity]
    estimated_power_flows: int


class RunResult(ToolResult,RunRecord):pass


class ResultsPage(ToolResult):
    run: RunRecord
    cases: list[CaseResult]
    evaluation: dict[str,Any] | None
    evaluation_scope: Literal['whole_run']
    total_cases: int
    next_cursor: str | None


class ExperimentSummary(OpenRecord):
    experiment_id: str
    name: str
    hypothesis: str
    strategies: list[str]


class ExperimentPage(ToolResult):
    experiments: list[ExperimentSummary]
    runs: list[RunRecord]
    next_cursor: str | None


class ComparisonResult(ToolResult):
    rows: list[dict[str,Any]]
    differing_fields: list[str]
    complete: bool
    paired_compatible: bool
    note: str


class CancellationResult(ToolResult):
    cancel_requested: bool
    run_id: str | None = None
    job_id: str | None = None


class StrategyRecordResult(ToolResult):
    record_id: str
    stage: str
    status: str
    spec: dict[str,Any]
    parent: str | None = None


class StrategyCommandResult(ToolResult):
    status: str
    record_id: str | None = None
    experiments: list[dict[str,Any]] | None = None
    next_action: str | None = None


class JobResult(ToolResult):
    job_id: str
    status: str


class ConditionChange(BaseModel):
    field: str
    before: Any
    after: Any


class ScenarioResult(ToolResult):
    scenario_id: str
    contract_version: str
    conditions: ScenarioConditions
    parent_id: str | None
    network_reference: str
    changes: list[ConditionChange]


class PreparedExperiment(ExperimentResult):
    scenario_id: str
    network_reference: str
    status: Literal['experiment_prepared']


class SourceBinding(BaseModel):
    specification_id: str
    specification_hash: str
    source_hashes: dict[str,str]
    test_hashes: dict[str,str]


class VerificationResult(ToolResult):
    record_id: str
    status: Literal['not_checked','checks_passed','checks_failed','stale']
    scientific_verdict: Literal['not_evaluated']
    verification_id: str | None = None
    tests_run: int | None = None
    skipped: int | None = None
    binding: SourceBinding | None = None


class ContractResult(ToolResult):
    version: str
    terms: dict[str,str]
    rules: list[str]
    workflows: dict[str,str]
    compatibility: str
    reporting: list[str]


class CatalogResult(ToolResult):
    example: Experiment
    strategies: list[str]
    metrics: list[str]
    assumptions: list[str]


class StrategyCatalogResult(ToolResult):
    strategies: list[dict[str,Any]]
    commands: list[str]
    command_schema: dict[str,Any]
    options_schema: dict[str,Any]
    records: list[dict[str,Any]]
    build_contract: str


class RLCatalogResult(ToolResult):
    defaults: dict[str,Any]
    models: list[dict[str,Any]]
    jobs: list[dict[str,Any]]
    algorithm: str
    energy_boundary: str


class BenchmarkSuite(ToolResult):
    suite_id: str
    protocol: str
    config: BenchmarkConfig
    fixture_hash: str
    ladder: list[int]
    common_ladder: list[int]
    tests: list[dict[str,Any]]


class BenchmarkCatalogResult(ToolResult):
    protocol: str
    defaults: BenchmarkConfig
    run_defaults: BenchmarkRunConfig
    tests: list[dict[str,Any]]
    strategies: list[dict[str,Any]]
    suites: list[dict[str,Any]]
    jobs: list[dict[str,Any]]


class BenchmarkResults(ToolResult):
    job: dict[str,Any]
    request: dict[str,Any]
    rows: list[dict[str,Any]]


class BenchmarkComparison(ToolResult):
    suite_id: str
    rows: list[dict[str,Any]]
    note: str


class ContinuousCampaignRecord(OpenRecord):
    campaign_id: str
    status: str


class ContinuousCampaignResult(ToolResult, ContinuousCampaignRecord):
    pass


class ContinuousCatalogResult(ToolResult):
    algorithm: Literal['node_ppo']
    defaults: CampaignConfig
    action_space: str
    campaigns: list[ContinuousCampaignRecord]
    legacy_note: str


class ContinuousResults(ToolResult):
    campaign: ContinuousCampaignRecord
    request: dict[str, Any]
    report: dict[str, Any] | None


class ContinuousCancellationResult(ToolResult):
    campaign_id: str
    cancel_requested: bool


RESULT_TYPES={
    'ev_get_continuous_rl_catalog':ContinuousCatalogResult,
    'ev_create_continuous_campaign':ContinuousCampaignResult,
    'ev_start_continuous_campaign':ContinuousCampaignResult,
    'ev_get_continuous_campaign':ContinuousCampaignResult,
    'ev_get_continuous_results':ContinuousResults,
    'ev_cancel_continuous_campaign':ContinuousCancellationResult,
    'ev_resume_continuous_campaign':ContinuousCampaignResult,
    'ev_get_contract':ContractResult,'ev_get_catalog':CatalogResult,
    'ev_get_strategy_catalog':StrategyCatalogResult,'ev_get_rl_catalog':RLCatalogResult,
    'ev_get_benchmark_catalog':BenchmarkCatalogResult,'ev_create_benchmark':BenchmarkSuite,
    'ev_start_benchmark':JobResult,'ev_get_benchmark':BenchmarkResults,'ev_cancel_benchmark':CancellationResult,
    'ev_compare_benchmark':BenchmarkComparison,
    'ev_save_experiment':ExperimentResult,'ev_get_experiment':ExperimentResult,'ev_add_cases':ExperimentResult,
    'ev_validate_experiment':ValidationResult,'ev_list_experiments':ExperimentPage,
    'ev_get_run':RunResult,'ev_start_run':RunResult,'ev_get_results':ResultsPage,'ev_compare_runs':ComparisonResult,
    'ev_cancel_run':CancellationResult,'ev_cancel_rl':CancellationResult,
    'ev_train_rl':JobResult,'ev_get_rl_job':JobResult,
    'ev_get_strategy_record':StrategyRecordResult,'ev_strategy_command':StrategyCommandResult,
    'ev_propose_strategy':StrategyRecordResult,'ev_specify_strategy':StrategyRecordResult,
    'ev_save_scenario':ScenarioResult,'ev_get_scenario':ScenarioResult,'ev_prepare_experiment':PreparedExperiment,
    'ev_verify_strategy':VerificationResult,'ev_get_strategy_verification':VerificationResult,
}
