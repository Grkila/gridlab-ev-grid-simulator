# Strategy research audit — 2026-09-10

This audit distinguishes algorithm conformance, implementation correctness, and
electrical-model validity. Passing software tests is not reproduction of a paper's
experiments. The nine catalog entries are reviewed individually. Reviewers were
assigned independently; corrective assignments follow their findings.

## Final disposition

**None of the nine entries establishes exact end-to-end reproduction of a research
paper.** LLF and valley filling now implement the cited optimization mechanisms
within documented model adaptations. MPC, voltage and RL remain materially
different algorithms/models. The four baselines have no exact-paper claim.

| Strategy | Corrected in this audit | Still not implemented or established |
| --- | --- | --- |
| Immediate | Shared finite-input validation; accounting/window checks retained | Household/LV/travel-data reproduction, taper, physically verified energy during nonconvergence |
| Fixed delay | Calendar-boundary tests and explicit same-day release contract | Tariff windows, location-aware release, deadline rescue |
| Randomized delay | Seed/support/order/midnight tests and explicit release contract | Per-ID nested randomness across fleet changes, adaptive release/deadline rescue |
| Capacity aware | External requests can no longer bypass admission or AC checks | Deadline feasibility, congestion-local optimal curtailment, proactive daily-kWh enforcement |
| Least laxity first | Replaced greedy dispatch with constrained smoothed optimization; analytical and overlapping-budget tests | Single-station theorem on this grid; max-min fairness under arbitrary overlapping budgets; scalable solver beyond fallback thresholds |
| Valley filling | Replaced cyclic descent with simultaneous ODC; convergence/energy-deficit diagnostics; full connected departures | Guaranteed finite-iteration convergence, day-ahead participant/forecast reproduction, network-feasible complete schedules |
| MPC | Fixed shared-deadline horizon bug, full variable guard, explicit plain-LLF fallback naming | Full ASA utilities, phases, pilots, BMS and tariff/PV model; fair deficit tie-break |
| Voltage | Causal initial baseline measurement, elapsed-time recovery, raw/applied intervention diagnostics, honest label | Historical three-phase/asynchronous paper controller and its unbalanced network experiment; full-paper equation validation |
| RL | Correct clipped-policy score derivative and episode-start time discount; numerical gradient tests | EV-GNN/DeepTOP/physical scheduling architectures; useful trained policy or generalization evidence |

All four baseline fixes were handled by a fixer after individual strategy reviews.
LLF, ODC, MPC, voltage and RL each received a corrective assignment. Other agents
then reviewed the changed code and numerical tests. Agent capacity required reusing
agents for successive strategy assignments; review and correction roles were
explicit, and final cross-checks used a different author where reported below.

The LLF extension uses a quadratic increasing concave utility on its feasible
laxity domain. It matches the scalar-budget smoothing solution, but with overlapping
budgets that choice can produce a non-max-min allocation. The dense solver has
size/time bounds: at default settings its quadratic size guard permits roughly
547 simultaneously constrained EVs, fewer with enough constraint rows. Larger
problems use explicitly reported plain LLF. Time checks are cooperative, not a
preemptive wall-clock guarantee. The public ID is retained, but its behavior has
changed; old fingerprinted runs remain historical evidence.

ODC's feasibility diagnostic covers each EV's power/energy bounds, not shared-grid
feasibility after projection. MPC and ODC now plan through connected departures;
the requested horizon is recorded for compatibility and may be extended beyond
192 intervals, subject to the variable budget. Neither assumes free shared capacity
outside a truncated horizon. Finite iterations and forecast errors remain material.

The detailed findings below describe the **pre-fix state** unless explicitly
identified as a remaining model limitation. The table above is the final status.

## Research sources and comparison boundaries

- LLF: [Chen et al., Smoothed Least-Laxity-First Algorithm for EV Charging](https://arxiv.org/pdf/2102.08610), equations 6 and 16–17, Algorithm 1.
- Valley filling: [Gan, Topcu and Low, Optimal Decentralized Protocol for Electric Vehicle Charging](https://smart.caltech.edu/papers/ContinuousEVCharging.pdf), energy feasibility equation 1 and ODC algorithm.
- MPC: [Lee et al., Adaptive Charging Networks: A Framework for Smart Electric Vehicle Charging](https://arxiv.org/pdf/2012.02636), sections IV–V.
- Voltage response: [Cardona et al., Decentralized electric vehicles charging control using only local voltage measurements](https://www.sciencedirect.com/science/article/pii/S0378779618301020). Accessible publisher text supports only a partial comparison; full equation-level validation remains unavailable.

## Shared discrepancies that remain

The simulator is a balanced, synthetic MV planning proxy. It has no physical LV
feeders, phase imbalance, charger-terminal voltage, measured battery acceptance,
or discrete EVSE pilot model. Aggregate downstream capacity estimates are scenario
assumptions. AC checks occur after proposed charging allocations; they are not
constraints inside a complete forecast power-flow optimization.

Continuous research controllers receive mandatory centralized AC safety reductions.
Voltage feedback also receives centralized budget admission. Immediate and delayed
baselines do not receive that protection; RL has a configurable binary shield.
These are different complete control systems. Reduced peaks must be assessed with
delivered energy, departure shortfall, interventions and violations.

Optimization sees connected sessions and causal baseline forecasts. It does not
see future arrivals or realized future demand. This differs from an offline
paper-reproduction dataset. No paper dataset, published performance percentage,
resource-augmentation bound or real-city operational claim has been reproduced.

## Findings and verification

### Least laxity first

The original controller sorted current slack and exhausted headroom in that order.
It did not implement the cited next-step laxity smoothing. With two identical EVs,
each needing 1 kWh in two hours at 1 kW, and a 1 kW shared budget, it assigned
`1, 0` instead of `0.5, 0.5`. Existing urgency-order tests accepted this discrepancy.
Multiple overlapping grid budgets also preclude blindly applying one scalar
threshold and then clipping it greedily. Any generalized constrained implementation
and its numerical fallback must be identified separately from the paper theorem.

### Valley filling

The original implementation used cyclic coordinate water filling. The cited ODC
uses simultaneous proximal EV updates based on one common broadcast. Eight sweeps
had neither a convergence certificate nor a residual. Impossible energy was silently
clipped: 20 kWh requested over four quarter-hour slots at 8 kW can deliver only
8 kWh, yet the diagnostic reported zero predicted deficit. Planning and safety
projection must remain distinct; feasible unconstrained charging profiles need not
remain energy-feasible after grid curtailment.

### MPC

The original truncated-horizon calculation assumed each EV could use its full
charger outside the horizon, ignoring shared bottlenecks. Two EVs needing 1 kWh
each over two hours, with a 1 kW shared limit and a one-step horizon, both received
zero initially and missed roughly 1 kWh by departure. A feasible schedule exists.
The variable guard also omitted deficit and peak variables.

The implemented objective remains delivery deficit followed by peak. ASA's broader
weighted utilities, tariff/PV inputs, demand-charge history, pilot discretization,
phase-aware current constraints and measured battery acceptance remain absent.
Solver time is configured **per LP stage**, as the GUI says; it is not a total
controller wall-clock limit. Symmetric deficits have no fairness tie-break.

### Voltage response

The cited historical, phase-specific charging-node approach is not the fixed
0.95–0.99 pu droop implemented here. Those thresholds and the 25% recovery increment
are local design choices, not verified paper parameters. The controller is
synchronous and uses the previous balanced MV block voltage. Its mandatory global
budget/AC overlay means protected traces cannot validate decentralized control.
Optional paper priority/economic/travel inputs are absent, and the paper's adequate
baseline-planning premise is not established for every configured scenario.
An initial missing measurement withholds an entire interval, and recovery depends
on step count. The full historical algorithm and its unbalanced-network experiments
remain unimplemented; the full paper equations could not be retrieved. The
[author repository](https://repositorio.unicamp.br/acervo/detalhe/1191020) marks the
record closed access. A fabricated historical rule would not close this gap.

### Verification baseline

Before edits, `python -m unittest discover -s tests -v` passed 107 tests in
175.185 seconds. Log: `artifacts/playground/research-audit-tests-before.log`.
This baseline did not detect the counterexamples above.

### Immediate

The immediate rule correctly respects connection windows, charger limits, battery
energy and efficiency. It is an uncontrolled baseline, not a paper reproduction.
Compared with [Muratori's residential study](https://doi.org/10.1038/s41560-017-0074-z),
the synthetic mixed-location MV model lacks household/travel-level resolution and
local LV concentration. Only primary source scope was accessible, not all equations.
Constant power/efficiency omit taper and subinterval dynamics. Nonconverged
intervals still credit requested energy under the simulator's accounting convention;
that energy is electrically unverified. Direct reset accepted some NaN/infinite
session inputs and nonintegral time indices; this shared validation defect was
assigned to a fixer.

### Fixed delay

This is an arrival-calendar-day release threshold, not a full time-of-use policy.
Arrivals after that day's release charge immediately. Thus an evening arrival
with start hour 00:00 does not wait for the following midnight. Departure before
release means no charging. One global release hour applies to all charging
locations, so default 23:00 systematically disadvantages workplace/public visits.
There is no end window, tariff calendar or deadline rescue. These are documented
baseline choices rather than a reproduced research algorithm. Boundary tests were
missing and were assigned to a fixer.

### Randomized delay

The release is the same arrival-day start plus a seeded jitter, not a random wait
after arrival. At 15-minute resolution the support is 0–3.75 hours in 16 equal
discrete steps; 4 hours is excluded. Releases cross midnight without being reset.
Input order does not affect draws because IDs are sorted, but adding an earlier
ID changes subsequent draws: fleet expansion is not nested per-vehicle randomness.
Other timesteps truncate the support; above four hours jitter is always zero.
No exact paper algorithm is claimed. Calendar, deadline and protection limitations
match fixed delay; explicit permutation and release-boundary tests were missing.

### Capacity aware

This custom EDF heuristic admits power against instantaneous budgets, then applies
global AC reductions. Passing external actions previously bypassed both protections
without changing the strategy label; a fixer was assigned that API defect. EDF
ignores laxity and has no deadline-feasibility guarantee. A constrained branch can
halve unrelated charging; the shield does not maximize feasible service. A daily
kWh budget is monitored after dispatch, whereas RL's shield actively admits against
it. These are distinct policy constraints even in a shared scenario. Thermal ageing,
physical LV assets and local phase constraints are absent.

### Reinforcement learning

This is a custom Bernoulli REINFORCE MLP. It lacks
[EV-GNN's graph representation/message passing and actor–critic architecture](https://www.nature.com/articles/s44172-025-00457-8),
[DeepTOP's learned activation-cost threshold, critic and index machinery](https://proceedings.neurips.cc/paper_files/paper/2022/file/b8bf2c0dd0b48511889b7d3b2c5fc8f5-Paper-Conference.pdf),
and the [on/off scheduling paper's two-port and phase-aware binary optimization](https://pubmed.ncbi.nlm.nih.gov/34770454/).
Those citations provide context, not implementation identity. The final source was
available only through the primary paper's indexed abstract.

The reviewer numerically demonstrated a clipped-logit gradient inconsistency:
at bias 30 the actual clipped policy is locally constant, yet training changed the
bias. Discounted returns also omitted the outer time discount for a standard
episode-start discounted objective. Both findings were assigned to a fixer.
Advantage normalization and clipping remain practical estimator modifications.

Historical four-episode training (seeds 12000–12003) evaluated on seeds 701/702.
Each requested 336 kWh. RL delivered 208.50/201.605 kWh and missed
127.50/134.395 kWh; immediate/capacity-aware missed 7.34/2.345 kWh. RL recorded
244/232 switches, 127/44 interventions and 10/5 voltage-violation intervals.
This poor model is not validated by pipeline success or by fixing training code.
No new convergence or generalization result is claimed. Stochastic training and
deterministic threshold evaluation also differ.

## Corrective evidence

- `tests/test_smoothed_llf.py`: 10 tests, including equal sharing, the paper's
  oscillation fixture, heterogeneous efficiency, overlapping and weighted budgets,
  numerical bounds and recorded fallbacks.
- `tests/test_valley_odc.py`: 5 tests, including the simultaneous first update,
  independent constrained-QP optimum, infeasibility and convergence diagnostics.
- `tests/test_mpc_deadlines.py`: 2 tests, including the previously avoidable
  shared-deadline shortfall and the complete LP variable-count guard.
- `tests/test_voltage_bootstrap.py`: 4 tests, covering causal initialization,
  failure-to-zero, elapsed-time recovery and protection intervention accounting.
- `tests/test_baseline_contracts.py`: 6 tests, covering finite inputs, delay
  boundaries, random replay and external-request protection.
- `tests/test_rl_gradient_audit.py`: 5 numerical tests, including joint-policy
  finite differences, saturated logits, empty initial slots and model round-trip.

Independent post-fix reviews passed the relevant 26 LLF/ODC/shared-strategy tests,
7 RL/MPC tests, and 10 voltage/baseline tests. These groups overlap the full suite
and must not be added as separate unique test counts. The Gan coefficient was
also checked against indexed primary manuscript Algorithm ODC and equation 6;
direct PDF fetching was intermittently unavailable.

All playground Python helper files are automatically included by
`service.implementation_fingerprint`; new LLF/ODC helpers therefore participate
in immutable run source hashes. Existing saved results and model weights were
not rewritten to appear as corrected evidence. Running app/MCP processes may
need restarting to load changed Python modules.

Final repository validation: **139 tests passed in 151.850 seconds**, including
32 new audit regression tests. Command: `.venv/Scripts/python.exe -m unittest
discover -s tests -v`; log: `artifacts/playground/research-audit-tests-final.log`.
The first post-edit full run hit an acceptance-worker timeout followed by a Windows
log cleanup lock; the unchanged acceptance test passed on the final rerun. That
failed attempt is retained in `research-audit-tests-after.log`, not represented
as a pass. The frontend TypeScript/Vite production build passed with its existing
bundle-size advisory (`research-audit-web-build.log`).

The real stdio MCP workflow passed with run `run-6a00cba223da4967`, experiment
`exp-e201b1d830c286c74320`, using fresh process imports and fingerprinted source.
Evidence: `artifacts/playground/evidence/strategy_workflow.json`; detailed local
run: `artifacts/playground/strategy-poc-runtime/runs/run-6a00cba223da4967`.
All five cases completed 132 intervals with eight EVs and 112 requested battery
kWh, no reported electrical/district/stage violations, no nonconvergence,
no fallback and no AC safety reductions. This small case establishes execution,
not comparative superiority. The other four strategies are covered by the
repository and dedicated review tests; this workflow did not retrain RL.

| Controller | Delivered kWh | Unmet kWh | City peak kW | Runtime seconds |
| --- | ---: | ---: | ---: | ---: |
| Capacity aware | 112 | 0 | 115797.929 | 10.98 |
| Smoothed LLF | 112 | 0 | 115797.929 | 11.06 |
| Valley ODC | 112 (rounded) | 0.000000000004 | 115772.899 | 11.46 |
| MPC | 111.9999997 | 0.0000003 | 115772.900 | 14.41 |
| Voltage droop | 112 | 0 | 115793.911 | 10.90 |

Minimum voltage was approximately 0.967548 pu in every case. **ODC reached its
eight-iteration limit in 57 intervals**; it did not claim convergence there.
Consequently the successful energy accounting is not an optimization-convergence
result. Solver tolerances explain the tiny numerical energy residuals above.
