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
