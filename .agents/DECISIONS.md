# Architecture decisions

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
