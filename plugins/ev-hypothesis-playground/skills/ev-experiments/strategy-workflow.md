# Typed strategy workflow

Read `ev_get_contract` and the live tool schemas first. Prefer `ev_propose_strategy`
with name, idea and research category, then `ev_specify_strategy(record_id, definition)`.
The complete definition requires objective, causal information enum entries, forecast,
actions (continuous_kw or binary_on_off), constraints, algorithm, fallback, research,
verification_tests (named repository test modules), and limitations. Parameters and
primary references are optional except references are required for reproduction or
adaptation. Engineering baselines need no invented citation. Planned test modules may
be specified before they exist; verification requires their implementation.

For a revision, call `ev_specify_strategy` with the prior record ID and a complete new
definition. Legacy REVISE cannot change forecast, actions, verification_tests or
limitations; it is retained for old records. A modern specification is validated again
before BUILD, including when accessed through the legacy adapter.

An explicit implementation request authorizes workspace coding and tests. In app chat,
select Implement and the saved specification ID; the next turn resets to automatic
mode. `ev_verify_strategy` executes the named repository tests with a 90-second budget
and saves counts, output and source/specification/test fingerprints. `checks_passed`
means those software checks passed; it proves neither full specification conformance
nor scientific superiority. Changes to bound source or tests make the report stale.
Evaluate with frozen scenarios, bounded experiments and measured run evidence next.

## Legacy strategy commands

Commands may be pasted into Codex or the experiment chat. `ev_strategy_command`
accepts the same text, or JSON with a `command` field. Read the live schema for
supported fields. IDs below are explanatory placeholders; use actual returned IDs.

```yaml
STRATEGY PROPOSE
name: deadline_headroom
idea: Allocate shared headroom using remaining charging slack.
objective: Meet departure energy requests within network limits.
research: adaptation
```

PROPOSE stores an idea. The assistant researches and adds references when specifying:

```yaml
STRATEGY SPECIFY
based_on: <saved strategy record ID>
information: [connected sessions, current baseline, known capacity budgets]
constraints: [nonnegative power, charger limits, battery energy limits, network limits]
algorithm: Sort by hours to departure minus required charging hours; allocate headroom in that order.
fallback: On missing electrical measurements request zero power and report the missing input.
references:
  - title: Smoothed Least-Laxity-First Algorithm for EV Charging
    url: https://arxiv.org/abs/2102.08610
    mechanism: Prioritize sessions with the smallest charging slack.
    difference: This specification is greedy LLF, not the published smoothed allocation.
```

```yaml
STRATEGY BUILD
based_on: <specified strategy record ID>
```

BUILD stores an implementation request and returns a complete coding prompt. A
matching existing name is not proof that the new specification was implemented.
Codex performs the coding work in the workspace and reports actual test outcomes.
Never call a new proposal runnable until the live experiment validator accepts it.

```yaml
STRATEGY COMPARE
scenario: <saved experiment ID>
candidates: [capacity_aware, least_laxity_first, valley_filling, mpc, voltage_responsive]
seeds: [11, 12]
max_cases: 10
max_runtime_seconds: 300
```

This prepares and saves the comparison. `ev_start_run` executes it. An RL candidate
also requires a frozen model in the scenario. Do not erase incompatible assertions;
explicitly revise them before changing candidates.

```yaml
STRATEGY CHALLENGE
scenario: <saved experiment ID>
candidates: [capacity_aware, mpc]
seeds: [11]
max_cases: 4
max_runtime_seconds: 300
variations:
  - fleet_sizes: [100, 1000]
```

Variations must use supported experiment fields. Earlier departure and forecast
error are not accepted as invented fields: extend the validated scenario model
first if the requested uncertainty is unavailable. Limits and capacities should
only change when they are the explicitly stated uncertainty under study.

REVISE takes `based_on` plus changed specification fields and preserves the parent.

## Controller implementation contract

New research-inspired controllers live in `src/mvgrid/novi_sad/playground/strategies.py`.
Implement `actions(sim) -> {session_id: kW}` and `observe(sim, interval)`. Inspect the
current source before editing. Use only permitted observations; full simulator
access does not authorize reading future sessions or realized future demand.
Decisions must be finite, nonnegative and bounded by charger and remaining energy.

Register the name in the experiment schema, strategy catalog and simulator factory.
Pass validated options through the worker. Preserve frozen options, dependency
hashes and diagnostics. Add GUI metadata so one experiment picker covers both
learned policies and other controllers. Do not automatically execute Python
submitted through MCP or dynamically import arbitrary user paths.

Use meaningful hand-checkable tests: slack ordering, demand smoothing, capacity
constraints, missed deadlines, observation causality, timeout fallback and energy
accounting. Follow repository integration checks. Cite which paper mechanism is
implemented and what differs; do not transfer published performance percentages.

Existing controllers: generalized constrained smoothed LLF, finite simultaneous
ODC valley filling, lexicographic linear MPC, and a custom voltage droop heuristic.
See `docs/strategy-research-audit.md` in the repository for paper discrepancies.
MPC first minimizes horizon
required energy deficits then peak; it uses a relaxed linear network forecast and
the simulator checks the applied action with AC power flow. Both optimization
controllers default to persistence forecasts. Previous-day mode reads observed
history, retains the known present value, and falls back to persistence where no
historical value exists. Both planners extend through connected departures, subject
to variable limits and explicit plain-LLF fallback. No future arrivals are exposed.
Voltage obtains a causal baseline measurement on initialization and requests zero
if measurements are unavailable; mandatory centralized safety may further reduce
its local request. Continuous and binary RL shields have different action constraints.
