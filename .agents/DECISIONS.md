# Architecture decisions

## 2026-09-10: User-selected voltage-regulated operating scenario

The user requested a more optimistic operating scenario with positive winter EV service and the neutral name **Voltage-regulated grid**. `operating_mode=regulated` freezes source voltage at 1.04 pu and shifts baseline input above 220 MW to other hours while preserving each day's input energy. Complete days are processed before departure-tail slicing; demand below the cap is unchanged. The same helper is used by experiments, benchmarks and RL training. Settings remain visible, and saved network metadata records the intervention. Pass thresholds remain 0.95–1.05 pu, full asset/stage ratings, and departure energy delivery. The as-supplied scenario is available explicitly. The original large-capacity run was cancelled and moved out of the visible catalog to prioritize the regulated 500-car reference / 5,000-car search study; its partial evidence is not a completed capacity result.

## 2026-09-10: Loss-inclusive consumption and corrected feeder reduction

The user clarified that supplied consumption includes network losses. New DemandConfig definitions and seasonal presets use `supply_including_losses`: solve the zero-EV net baseline to match AC supply within 0.01 kW, then add EVs and incremental losses once. Explicit `load` inputs and historical saved records without the field retain load-side semantics. Capacity ratings and thresholds are not relaxed. The reduced feeder now uses downstream-current-weighted worst-path impedance instead of total load times average full-path impedance. This corrects excessive voltage drop while retaining a conservative first-order voltage screen, not an exact loss or AC reduction. The loss-weighted alternative was tested but not substituted for weakest-path voltage. See docs/baseline-loss-diagnosis.md for paired detailed evidence, limitations, and separate demand-response/voltage-support hypotheses.

At the user's request, older experiment/run/benchmark entries were moved out of the runtime catalog to `artifacts/playground/retired-before-loss-correction-20260910`; automatic approval review rejected permanent deletion. Five fresh gross-input experiment definitions and a new capacity benchmark replace the visible test set. Models, strategy records and chats were retained.

## 2026-09-10: Centralized binary RL in the shared simulator

The RL workspace uses a NumPy neural Bernoulli REINFORCE policy, shared over current connected EVs with global grid features. It requests binary on/off charging; a separately reported optional admission/AC shield removes whole requests. Training samples independently seeded seasonal daily amplitude/shape and sessions, completes overnight departures, and penalizes violations without early stopping. Evaluation uses immutable model JSON, held-out seeds, frozen seed-specific shared demand and the experiment's normal stop policy. Reward edits during evaluation rescore only; new learning requires a fresh job. Optional daily kWh budgets cover baseline+EV grid-load energy excluding AC losses, reset at midnight, and apply to all comparison strategies. Training completion is not policy acceptance; the four-episode diagnostic underperformed baselines. Details and evidence: docs/models/ev-rl.md.

## 2026-09-10: Package and folder boundaries

Source code uses a `src/mvgrid` package. The original GUI workflow is isolated under `legacy`; Novi Sad code is under `novi_sad`. All repository paths are defined in `mvgrid.paths`, so commands work outside the repository directory.

## 2026-09-10: Reference artifact exception

One challenge reference set remains versioned under `artifacts/novi_sad/reference/`, including the large pandapower JSON and HTML map. This favors an inspectable handoff over repository size. Future large snapshots should use a GitHub Release rather than normal Git history.

## 2026-09-10: Cache and reproducibility boundary

Python pickle and live OSM caches remain ignored under `data/cache/`. A manifest with hashes and dependency versions provides traceability. This is not described as clean-clone reproducibility.

## 2026-09-10: EV experiment evidence boundary

EV experiments use strict, immutable definitions and fingerprinted local runs. Fleet size, seed, and implemented charging strategy form the case matrix; other parameter changes create revisions. Incomplete, cancelled, budget-limited, or violation-stopped runs are not passes. Provenance fields label interpretation but do not alter calculations.

The experiment network retains only explicitly active sources and their downstream demand. A city-total demand input is scaled by the retained calibrated-MW fraction; excluded demand is not reassigned. Early stopping on monitored district or upstream-transformer violations is the safe default, while full-horizon overload studies opt out explicitly.


## 2026-09-10: Primary GUI and CLI lifetime

The green React GUI replaces Streamlit as the primary application while sharing its simulation service. Codex chat streams observable JSONL tool events from the native CLI. A GUI-owned loopback run broker decouples simulation lifetime from the CLI process; direct child workers were observed to be reclaimed when the CLI exited. Runtime-directory matching prevents the broker from silently using another experiment store.

## 2026-09-10: Aggregate district capacity instead of MV/LV assets

The user chose estimated district kW budgets while retaining the small pandapower network. No individual 20/0.4-kV or 10/0.4-kV transformers are added. Delivery-group identities retain supply assignments; land-use mixture and EV district placement are separate. Default central budgets use adopted delivery-station apparent-power ratings with explicit power-factor and planning-margin assumptions, independent of the experiment demand curve. Low/high capacity scenarios are sensitivity assumptions. Frozen per-district overrides include provenance. District-capacity violations and upstream electrical violations are separate checks; either can stop an ordinary run. Such stops are constraint events, not physical protection trips.

## 2026-09-10: Whole-city capacity alignment to supplied estimates

The user explicitly restored NS1, NS6 and FUT to align the simulator with a whole-city 2025 capacity image. The playground generator distributes 299 MW at 20 kV and 179 MW at 10 kV among delivery equivalents using original station-MVA proportions and PF 0.97. Transformer percent impedances change with the MVA base to preserve physical impedance. Feeder ratings and 110/35-kV ratings retain their original assumptions. The separate 80% district planning factor is retained (382.4 MW total). All image figures and interpretation are versioned in `data/novi_sad/reference/inputs/capacity_estimate_2025.json` and embedded in the generated network and new run records. Transmission 430 MW, LV 120 MW, unspecified transformer 150 MW and 25% reserve are reference-only because compatible assets and operating conditions are absent. Successive network layers are not summed into load capacity. This is calibration to a supplied estimate, not independent utility validation.

## 2026-09-10: Account for all image capacities with usable reserve

The user requested all figures be reconciled and clarified that the 25% reserve may be used but full capacity may not be exceeded. This supersedes the prior reference-only aggregate treatment and 80% district factor. Full district ratings total 478 MW; additional aggregate constraints model transmission 430 MW and downstream transformer/LV stages of 150/120 MW. The unspecified transformer figure is explicitly assigned to a downstream stage as a scenario assumption. Editable baseline/EV LV shares default to 0.5/1.0; demand is not duplicated. Reserve use is reported above 75%; violations occur above 100%. These are aggregate overlays on MV AC power flow, not invented physical LV assets.

## 2026-09-10: Remove only three public charging hubs

The user excluded NS1-HUB, NS6-HUB and FUT-HUB while retaining their stations, regular demand blocks and all city demand. Generator output is 96 buses, 72 lines, 15 transformers, 56 demand blocks and 10 public hubs. Full capacity totals and usable reserve remain unchanged. District placement with public charging in a hubless district fails validation rather than randomly failing during a run.

## 2026-09-10: Remove the three supplies and preserve city demand

The user clarified that NS1, NS6 and FUT supply stations must also be removed, with demand rebalanced. A shared preparation reassigns their feeder branches largest-first to retained 20-kV supplies by projected utilization. All 492 former-source members remain in the 2,648 city total. Their feeder impedances remain planning equivalents, not newly measured routes. Aggregate 20-kV capacity is redistributed across the four retained 20-kV sources; all image capacities and usable reserve are preserved. The generated network and detailed diagnostic share this reassignment. The API map cache keys on file revision.

## 2026-09-10: Shared controller and strategy development contract

All controllers use the same experiment replay and per-session kW adapter; RL retains binary action semantics. Four continuous POCs use causal observations and explicit forecast options with documented fallbacks. Strategy development records are immutable. MCP BUILD returns a coding handoff and never evaluates submitted code; an explicit complete BUILD message enables repository implementation for that Codex chat turn only. Registry membership does not prove specification conformance or successful tests. Catalog refresh must preserve an already edited experiment draft.

## 2026-09-10: Isolate comparison case failures

Multiple selected strategies imply a comparison batch: an individual limit stop, hard assertion failure, or controller exception cannot skip the remaining cases. Cancellation and total runtime budgets remain global. Single-strategy early rejection is preserved. GUI multi-selection defaults to full trajectories; explicitly stopped/error cases remain incomplete even when all cases have been attempted.

## 2026-09-10: Correct paper mechanisms without claiming model reproduction

Research review replaced plain LLF dispatch with an explicit constrained quadratic-utility smoothing formulation and cyclic valley descent with synchronous ODC. Existing IDs remain stable; immutable source fingerprints distinguish historical runs. Optimization covers all connected departures, bounded by variable limits, instead of assuming unconstrained capacity after a truncated horizon. Plain LLF remains a named numerical/resource fallback. Mandatory AC protection and the synthetic balanced MV boundary remain. Voltage is explicitly a custom droop heuristic; RL remains a custom REINFORCE prototype. Missing paper data, phase/pilot/BMS models, full voltage algorithm and policy-quality evidence are recorded in `docs/strategy-research-audit.md`, not claimed implemented.


## 2026-09-10: Recoverable chat and bounded MCP evidence

Chat readiness is published after cleanup under the same lock as its single-active-turn gate. Persistent request IDs make accepted POST retries idempotent. Turn/entry sequences support chronological rendering and delta polling with explicit resynchronization. Full completed tool output is archived separately; bounded previews never replace the evidence. Context uses exact pinned constraints and immutable-ID retrieval hints, not automatic memory summaries. Derived case summaries accelerate MCP reads while preserving original detailed artifacts and whole-run evaluation semantics. See `docs/chat-mcp-reliability.md`.

## 2026-09-10: Frozen ten-test benchmark

Benchmark suites freeze network, demand, district, capacity limits and nested deterministic EV session pools. Capacity scans retain failures and unknowns without assuming monotonic feasibility; the displayed capacity is the largest passing tested fleet, with explicit ceiling and baseline statuses. Every seed must complete departures and satisfy grid limits. Shared-fleet comparisons depend on the selected cohort and are excluded from cross-run comparisons. Implementation/settings fingerprints separate candidate versions. Benchmark workers reuse the shared simulator and worker lock. See `docs/benchmark.md`.


## 2026-09-10: One versioned agent contract across MCP, plugin and chat

Canonical Python rules generate plugin skill/assets and render MCP/chat guidance. Typed algorithm and scenario tools add strict structure while legacy records/tools remain usable. Software verification binds actual unittest counts to immutable specification/source/test revisions; passing checks do not imply scientific acceptance. Scenario conditions and network hashes are frozen separately from experiment choices. Explicit saved-spec implementation mode grants editing for one turn; focus routing otherwise preserves planning/explanation intent. Installed plugins pin the compatible contract version and are regenerated/reinstalled through the plugin update workflow. See `docs/agent-contract.md` and independent review `docs/agent-contract-validation.md`.

## 2026-09-10: Per-node EV load aggregation
User requested controllable total node demand. Use homogeneous cohorts internally and continuous equal sharing, retaining arrival/departure, charger, efficiency and energy constraints. Preserve individual mode and freeze aggregate_ev_nodes in benchmarks; reject binary RL. Power targets affect EV load only. Cohort policy can change greedy priority and safety behavior, so run new evidence rather than claiming all controller results identical.

## 2026-09-10: continuous benchmark PPO

Continuous node PPO uses the shared node allocator and frozen benchmark fixtures. The optional maintained SB3 backend has exact committed-update checkpoints and disjoint train/validation/test seeds. Canonical MCP/plugin/chat guidance distinguishes it from historical binary REINFORCE. See docs/continuous-rl.md and docs/continuous-rl-validation.md.

Curriculum scaling explicitly uses capacity-aware passing tested bounds after an attempted LLF65544 replay failed service under unchanged input hashes. That failed evidence is retained,not accepted. LLF and valley-filling remain mandatory held-out competitors,including strongest original tested fleet and105% thereof. Unknown comparative electrical evidence yields inconclusive. No trained superiority follows from software checks.

## 2026-09-10: comparison is the RL objective

User clarified that RL should outperform other policies; reaching80,000EVs alone is not success. Replacement campaign objective is `outperform_baselines`. All seven non-MPC algorithms receive identical validation/final-test cases; service/grid feasibility leads ranking,paired peak differences break ties only on fully served feasible cases.80k/84k remain explicit stress probes in the replacement request,with target attainment reported separately and never sufficient for superiority. Unknown evidence and missing comparator coverage prohibit a comparative winner. Prior queued target-only campaign was cancelled withzero training time.

## 2026-09-11: Explicit whole-day charging schedules

Experiments expose home-only and whole-day schedules; the latter uses editable linked percentage sliders that always sum to100%. Standard benchmark suites freeze one schedule, with whole-day shares70%home/20%workplace/10%public across allten tests. Shared versioned visit generation covers home17:00-21:00 to next-day09:00, work07:00-10:00 to15:00-19:00 and public00:00-23:45 with3-4hour dwell. This is one visit per vehicle per day, not repeated intraday travel. Legacyexperimentgeneration and originalhomebenchmarkpools remain compatible. Profileversion and expandedpoolprefix checks protect frozen suites. Night-delay policies remain unchanged and mayfaildaytimeenergyservice. See docs/whole-day-charging.md.

## 2026-09-11: Presentation integration

Use a separate Vite presentation entry with Reveal navigation, one persistent Three.js scene and one persistent same-origin app iframe. The bridge only changes UI views/stages; it cannot execute commands. Keep direct-study findings distinct from live-run evidence and illustrative RL/3D visuals. High-contrast dark backgrounds and dark text on lime controls implement the presentation preference. Details: docs/presentation.md.

Presentation revision: use exact piecewise interpolation on cached OSM road geometry for cars; keep synthetic city/grid provenance explicit. Animate saved results as visual reveals. Demo prompts only fill the real chat composer; the presenter chooses whether to send. Use concise Serbian presentation copy and Serbian embedded chat controls.

2026-09-11 showcase defaults: prefer the verified 10,000-EV saved run when no explicit run is supplied. Keep benchmark status and synthetic PPO demo labels visible. Chart transport reads one case at a time and omits only unused non-RL per-vehicle traces; no simulation or stored evidence changes. Simulator replacement is an adapter/validation extension, while selected detailed replay already exists.
