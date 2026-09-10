# Project memory

Last verified: 2026-09-10

## Purpose

The Schneider challenge fork adapts the upstream OSM MV-grid generator into one unified Novi Sad planning workflow. The legacy GUI remains available under `src/mvgrid/legacy/`.

## Verified reference baseline

- Status: `INTERNAL_CONSISTENCY_PASS`
- 2,648 loads; 21,783 buses; 21,759 lines; 15 transformers; 9 external grids
- Nine radial source islands using NS1, NS2, NS4, NS5, NS6, NS7, NS9, RIM, and FUT
- Base load 214.854 MW; minimum voltage 0.956792 pu
- Maximum line loading 72.2904%; maximum transformer loading 88.3325%
- Evidence: `artifacts/novi_sad/reference/reports/novi_sad_validation_report.json`

## Durable caveats

- The demand points, feeder routes, several station coordinates, associations, and equipment parameters are inferred.
- The annual energy is a calibration input and the peak is derived with a 1.64 peak-to-mean ratio.
- `data/cache/data.pkl` is ignored. Its SHA-256 is recorded in the input manifest, so the reference set is traceable but a clean clone is not bit-for-bit reproducible.
- Large reference artifacts are kept in Git for the challenge handoff. Regeneration will create large diffs; do not add additional snapshots.
- The EV hypothesis playground uses a separate experiment network and immutable, fingerprinted run manifests. It screens bounded scenarios; it does not establish utility-validated behavior or maximum hosting capacity.
- Excluded source demand is not redistributed. City-total demand inputs are scaled by retained calibrated-MW source share; active-source inputs are already scoped to retained sources.
- Runs stop on the first monitored district or upstream-transformer violation by default. Partial stopped evidence cannot pass or support paired comparisons.


## EV playground implementation

- Loss/voltage correction verified 2026-09-10: 200 tests pass (`artifacts/playground/regulated-tests.log`), frontend build and desktop/mobile benchmark checks pass. Branch-current-weighted weakest-path reduction replaces average full-path impedance. New metered consumption inputs include losses and reconcile AC baseline supply within 0.01 kW; explicit `load` and historical records retain load-side semantics. The separate 150 MW net-load workflow gives minimum voltage 0.975102 pu, line loading 50.3952%, transformer loading 53.2799%; detailed snapshot evidence is in `evidence/model_validation.json`. This remains a synthetic approximation, not as-built validation.
- User-selected **Voltage-regulated grid** mode uses 1.04 pu source voltage and baseline peak shifting to 220 MW with each day's energy preserved. Settings are visible and frozen; grid acceptance limits are unchanged. Original assumptions remain selectable. Five fresh regulated experiments are in the visible catalog; older experiments/results are recoverably archived outside runtime after permanent deletion was blocked. Current preview: port 8533. Full methodology and evidence: `docs/baseline-loss-diagnosis.md`.

- Centralized binary RL is available in the primary GUI: editable REINFORCE training/rewards, seeded day randomization, optional shield and daily total-load energy budget, immutable model selection, held-out comparisons and charger timelines. Four-episode end-to-end verification completed on 2026-09-10 but performed poorly (RL unmet 127.50/134.395 kWh vs immediate/capacity-aware 7.34/2.345 kWh). Do not call this model validated or superior. See `docs/models/ev-rl.md` and `artifacts/playground/evidence/rl_verification.json`.
- RL integration verification (2026-09-10): 99 repository tests passed, including 15 independent RL adversarial checks; real HTTP training/cancellation and 17-tool stdio lifecycle passed; TypeScript/Vite production build passed. Severity findings and fixes are recorded in `docs/models/ev-rl.md`. Logs: `artifacts/playground/rl-unittest.log`, `rl-mcp.log`, `rl-api.log`.

- The active playground has six sources after removing NS1, NS6 and FUT: 12 transformers, 76 buses, 58 lines, 42 demand blocks and 10 hubs. Their 492 former demand members (39.517377 MW reference demand) are reassigned; all 2,648 city demand members remain.
- Retained demand share is 1.0. Playground delivery equivalents are calibrated to user-supplied image totals of 299 MW at 20 kV and 179 MW at 10 kV; central district budgets now total 478 MW with usable reserve. The original detailed reference file remains unchanged. Evidence: `scripts/verify_capacity_alignment.py` and `artifacts/playground/evidence/model_validation.json` (2026-09-10).
- January preset: 120,000 MWh /31 days; June: 76,000 MWh /30 days. Worst case multiplies every configured day by1.20; annual growth compounds3% by years_ahead. These are user-supplied scenario assumptions.
- Primary GUI: React in web/, served locally by scripts/run_playground_app.py. Streamlit is a diagnostic alternative. Charts use clock time with15-minute data.
- Codex CLI chat is real, not simulated. The loopback app broker owns chat-started simulation workers so they survive CLI exit. Live evidence: artifacts/playground/evidence/codex_chat.json.
- Final acceptance status is maintained in docs/acceptance-review.md and artifacts/playground/evidence/testing.json; historical stage passes are not final GUI acceptance.
- District-capacity extension uses the reduced network and omits individual MV/LV assets by user choice. Thirteen delivery groups have fixed central kW estimates, low/high sensitivity factors and provenance-bearing overrides. `fleet.district_mix` selects reproducible car placement independently of charging-use mix. Both aggregate district budgets and upstream electrical constraints are checked. Evidence: `docs/district-capacity-review.md`; 52 unittest checks and the expanded real MCP lifecycle passed on 2026-09-10.

- Capacity alignment acceptance (2026-09-10): 54 unittest checks, real stdio MCP lifecycle, React build and full-day 150-MW electrical check passed. Details and boundaries: `docs/capacity-alignment-2025.md`.

- Whole-image extension: aggregate transmission 430 MW, downstream transformers 150 MW (assumed interpretation), and LV 120 MW are enforced alongside MV delivery ratings. User clarified reserve is usable: 75% starts reserve use; 100% is the limit. Editable LV baseline/EV shares default to 0.5/1.0; they are scenario assumptions. New results freeze shares and report stage loading, headroom and reserve use. See `docs/capacity-alignment-2025.md`.

- The former hub-only exclusion was superseded by explicit removal of NS1, NS6 and FUT supplies plus demand rebalancing. Current GUI is port 8520; Network shows 3 excluded sources and 100% retained demand.

- Strategy workflow verified 2026-09-10: nine registered controllers include LLF, valley filling, linear MPC, voltage feedback and RL. Immutable STRATEGY commands are exposed through MCP and GUI; explicit complete BUILD chat turns use workspace-write, subsequent ordinary turns reset to read-only. Combined suite99 passed; actual MCP5cases x132intervals, native proposal chat and headless GUI passed. See docs/strategy-development.md and artifacts/playground/evidence/strategy_workflow.json. POCs establish execution, not controller superiority.

- Comparison continuation verified 2026-09-10: multi-strategy worker batches continue after per-case grid stops, controller exceptions and failed assertions. Eight independent regression tests and real two-strategy runs passed. GUI multi-selection disables per-case stopping by default; explicit early stopping still yields incomplete case evidence. See docs/models/ev-playground.md and evidence/comparison_continuation.json.

- Research audit 2026-09-10 supersedes original strategy algorithm descriptions: LLF now uses constrained smoothing; valley uses simultaneous ODC with residual/deficit diagnostics; both optimizers cover connected departures. Voltage bootstraps causal baseline measurements; RL clipping/time-discount gradients and external capacity-aware protection were corrected. 139 tests passed, frontend build passed, fresh MCP run `run-6a00cba223da4967` completed 5 x 132 intervals. ODC hit its iteration limit in 57 intervals; no paper reproduction or RL quality claim. Full discrepancies and evidence: `docs/strategy-research-audit.md`.

- Chat/MCP reliability verified 2026-09-10: 152 unittest checks passed; isolated real-HTTP/fake-CLI browser acceptance passed 10 recovery, cancellation, transcript and evidence checks with no page errors. Real stdio MCP lifecycle and TypeScript/Vite build passed. Summary reads use derived caches; tool output remains retrievable; chat restores active work and pins exact constraints. Synthetic 1 MB storage check: zero detail reads on warm summaries, 239-byte unchanged poll. See `docs/chat-mcp-reliability.md`, `scripts/verify_chat_gui.cjs`, `scripts/verify_chat_storage.py`, and `artifacts/playground/chat-*.log`.

- Standard benchmark verified 2026-09-10: exactly ten frozen scenarios with dynamic strategy discovery, shared replay hashes, all-seed pass rules, citywide/district capacity ladders, common-fleet headroom, explicit unknown/baseline/ceiling statuses, GUI matrix/charts and six MCP tools. Full suite165 passed; real run `bench-33905f6834a84fac` completed30 cells across immediate/capacity-aware/MPC plus cancellation; ten-car ceiling is workflow evidence only. Normal capacity reached ceiling; worst-day grid failed at zero EVs. Frontend build and desktop/mobile acceptance passed. See `docs/benchmark.md` and `artifacts/playground/evidence/benchmark_verification.json`. Fresh preview runs on port8532; older port8520 process was not restarted.


- MCP/plugin/chat standardization verified 2026-09-10: canonical contract1.0.0, typed strategy/specification/verification and frozen scenario workflows, focused per-turn chat permissions, generated plugin synchronization and startup version pin. Independent validator accepted after adversarial fix/retest loops. Final full suite196 passed (147.587s), including21 independent tests; browser11 checks, real stdio32-tool lifecycle, benchmark discovery, build and live app passed. Personal plugin installed0.1.0+codex.20260910174816. Scope fixture explicitly measures load after concurrent gross-supply default change; all assertions preserved. No paid-model behavior/scientific superiority claim. See docs/agent-contract.md, docs/agent-contract-validation.md and evidence/agent-contract-validation.json.

- Benchmark matrix now reports concrete tested counts, explicit unknown maximum at a search ceiling, zero-car voltage and line loading, and stage margin/overload in MW. Production web build and desktop/mobile GUI checks passed (2026-09-10).

- User-selected doubling benchmark launched as bench-9b179943271740b0 (suite-3e709edbb01b3c69755e): zero control, then 2..32768 powers of two, stop first failure/unknown, retain observed bracket; all three strategies, regulated assumptions, seed 41001. Follow live state before claiming completion. Doubling integration suite: 17 tests passed.

- Active uncapped hosting-capacity run bench-c05c64724ee6497f / suite-40cbac52af3664f7d5b3 replaces capped doubling run. until_failure=true: zero baseline, unbounded powers of two, preserve first failed doubling, refine local boundary to adjacent integers. Frozen seed mechanism extends pools on demand. Nonconvergence is incomplete, not failed. Eighteen benchmark integration tests passed; inspect live results before claiming outcomes.

- EV scaling diagnostic: scripts/profile_ev_scaling.py, docs/ev-scaling-profile.md, artifacts/playground/ev-scaling-profile.json. 128..65536 EV synchronized 18:00 snapshots; grid stays 76 buses/52 loads. Vehicle/controller work dominates large fleets. MPC optimizes at128 but falls back at500+ in this snapshot. Concurrent benchmark means timings are indicative, not controlled throughput measurements.

- Node EV aggregation implemented (docs/node-aggregation.md). step_node_loads sets per-node total EV kW; homogeneous internal energy/deadline cohorts, weighted vehicle counts, no extra buses. 65536 synchronized EVs become42 groups; MPC2563variables solves without fallback. 206 full tests and18 benchmark integration tests passed. New aggregated uncapped run bench-7558936000a2407c / suite-19f52a8c3215ac54a015; prior individual run cancelled for implementation change. Fresh results required because scheduling differs.

- Full non-MPC benchmark running: bench-c0c965da89ab4b2d, suite-19f52a8c3215ac54a015, seven continuous algorithms and70cells, aggregated nodes, regulated baseline, seed41001, uncapped doubling. RL excluded as incompatible binary policy. Completed full-horizon base/aggregate comparison in docs/aggregation-validation-report.md; verdicts match tested cases but MPC4096 uses different fallback behavior and is now excluded. Do not infer completed capacity from launch.

- MPC retired from app views at user request: shared visibleControllers filter removes picker/catalog entries, historical cases, benchmark columns and comparison rows, and displayed exports. Historical files remain immutable, preserving other controller evidence in mixed runs. Strategy templates/settings no longer promote MPC. Eight available UI controllers (including optional RL); active full benchmark has seven compatible controllers. Production build and desktop/mobile GUI passed.
