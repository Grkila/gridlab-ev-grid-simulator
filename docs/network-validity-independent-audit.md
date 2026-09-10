# Independent audit: what network failures this model can establish

Audit date: 2026-09-10. Read-only inspection of the current reduced artifact, generator, simulator, reference construction and saved comparison evidence. No network parameters were changed. The earlier 42-test acceptance concerned software behavior and reproducibility, not real-network validity. Public source documents were not independently reverified in this audit.

## Verdict

**Accept as a synthetic, balanced MV steady-state experiment model. Reject as evidence of real Novi Sad failure thresholds, individual distribution-transformer hosting capacity, or protection operation.** The program really runs pandapower and tests its modeled assets, but several relevant assets and operational mechanisms are absent. The detailed reference shares important assumptions and cannot independently validate them.

The most consequential omission is **no 20/0.4-kV or 10/0.4-kV transformers and no LV buses or LV feeders**. The thousands of entries named “synthetic transformers” are demand service points, not transformer devices with kVA ratings. A block currently represents aggregated MV-connected demand, not an electrically modeled neighborhood transformer and its customers.

## Directly verified electrical inventory

Loaded `data/novi_sad/playground/reduced_network.json` through `src/mvgrid/novi_sad/playground/network.py:build_network` and inspected its tables:

- 77 buses, 53 demand blocks, 12 transformers, six external grids.
- Bus nominal voltages: 110 kV (6), 35 kV (8), 20 kV (25), 10 kV (38). Zero buses below 1 kV.
- Zero transformers with LV nominal voltage below 1 kV, zero switches and zero controller objects.
- 2,156 retained synthetic service points; allocated reference peak totals 175.336664 MW.

| Station equivalent | Ratio | Modeled `sn_mva` |
|---|---:|---:|
| NS2 | 110/35 kV | 51.5 |
| NS4 | 110/35 kV | 126 |
| NS5, NS7, NS9, RIM | 110/20 kV | 63 each |
| LIMAN, CENTAR, PODBARA, IND | 35/10 kV | 32 each |
| SEVER, TELEP | 35/10 kV | 16 each |

These are **station equivalents**, not a verified inventory of individual transformer banks. All 12 currently have `parallel=1`, `df=1`, `vk_percent=12`, `vkr_percent=0.45`. Treating a station's aggregate installed MVA as one transformer does not establish individual bank loading or N-1 capability.

`src/mvgrid/novi_sad/model.py:add_transformer` states “generic planning assumption; rating from EDS table.” It sets the common impedances above, generic iron losses, no-load current 0.10% and phase shift zero. The reducer copies these parameters; copying does not convert assumptions into measurements. The source table is `data/novi_sad/reference/generated/novi_sad_seeded_substations.json`, attributed there to EDS planning data, base year 2024. Its source values have not been checked against a current asset register here.

The seeded NS5 ratio is `110/20/10`; the reference builder's `direct_20kv` branch models it as a two-winding 110/20 equivalent using installed MVA. That simplification is material if real loading is shared between voltage sections. It must not be presented as independently verified 20-kV-only usable capacity.

## Why the service-point CSV is not a transformer inventory

`data/novi_sad/reference/generated/novi_sad_synthetic_transformers.csv` contains location, land-use class, annual energy and allocated peak demand. It contains no transformer kVA nameplate, impedance, LV voltage, thermal class or protection setting. Its provenance explicitly says “synthetic land-use allocation; not a verified utility asset.”

`src/mvgrid/novi_sad/model.py` creates each entry with `pp.create_load` at a feeder's MV bus. It does not create an MV/LV transformer there. Consequently, optional replay into the large reference also cannot reveal omitted MV/LV overloads, LV voltage drops, service cable loading or single-phase imbalance.

## Nameplate, planning budget and operational limit are different

- `sn_mva` is the adopted station-equivalent apparent-power rating. The simulator reports pandapower transformer loading and compares it to a configurable global loading threshold (100% by default).
- `source_capacity_kw` and `delivery_capacity_kw` are rating × 0.97 × 1,000. They are active-power planning proxies at an assumed power factor, not guaranteed import headroom. Actual losses/reactive demand enter the subsequent power flow.
- Reference demand routing already uses an 86% allocation margin and a below-90% transformer baseline gate, documented in `docs/models/novi-sad.md`. Feeder parallel circuits are selected from assigned demand using a 72% target and at least two circuits (`model.py:add_line`). Spare capacity is therefore partly designed into the synthetic model.
- This creates a circular hosting-capacity risk: baseline demand determines inferred circuit capacity, then that inferred capacity is used to estimate additional EV headroom. The batched line-construction path repeats the same rule. A result can be internally consistent while largely reflecting the chosen construction margin instead of observed infrastructure.
- The model has no measured seasonal/temperature derating, bank availability, operator transfer limits, firm N-1 limits, tap-control behavior, thermal aging or relay time-current settings.
- Six external grids hold 1.02 pu at their 110-kV buses. There is no modeled shared upstream transmission bottleneck, source outage sequence or verified cross-source switching arrangement.

A configurable threshold is appropriate for an experiment, but changing it changes an assumption. A 1% threshold used in UI tests deliberately produces a counterexample; it says nothing about a real equipment failure.

## What “failure” currently means

`src/mvgrid/novi_sad/playground/simulation.py:Simulator.step` runs balanced steady-state `pp.runpp`. It checks all retained bus voltages and line/transformer loadings against configured limits. A failure means **a modeled constraint violation, or numerical non-convergence**.

Default `stop_on_violation` stops further simulation after recording the offending interval; the worker preserves incomplete evidence. This is a software stopping rule, not a simulated circuit breaker trip. There is no trip, isolation, outage propagation, fault-current calculation, restoration or damage model. Numerical non-convergence cannot by itself be called voltage collapse or a physical outage.

The simulator updates EV delivered energy using commanded charging power for the entire offending interval, including when power flow does not converge. Its code explicitly identifies the absence of a protection model. Thus reported energy is demand-scenario accounting, not verified electricity delivered during an actual failed supply state. Fifteen-minute snapshots also cannot resolve sub-interval peaks or protection timing.

The capacity-aware heuristic allocates using block and source budgets, then repeatedly halves all charging if AC constraints are violated. It can end by removing all EV power and still report a baseline violation. It is a bounded feasible-action heuristic, not an optimal local congestion controller or proof of maximum hosting capacity.

## Reduction accuracy and exclusions

`network.py:reduce_reference` retains station transformer chains and 35-kV links, but replaces downstream trees with demand-weighted path R/X and bottleneck/fraction current equivalents. It omits equivalent-feeder capacitance and represents their length as 1 km with total impedance embedded in per-km values. These lengths must not be read as physical cable lengths. Shared-feeder coupling is approximated, and within-block EV placement disappears. A charger at the end of a weak branch and one near the station can become identical within a block.

Each delivery receives an illustrative 1-MW hub with zero baseline demand, not an observed charger installation. EV and baseline reactive power both use fixed 0.97 power factor. Land-use curves, EV sessions and allocations remain assumptions.

NS1, NS6 and FUT are explicitly excluded. City-total input is multiplied by 0.8160733804473949, the **synthetic reference peak-demand share**, not a measured share of monthly energy. That assumes the excluded and retained areas have compatible temporal demand shares. Results apply to the retained six-source proxy, not the whole nine-source city. Four legacy delivery associations and most station coordinates are inferred; `docs/models/novi-sad.md` documents this uncertainty.

Saved evidence `artifacts/playground/evidence/model_validation.json` contains one selected no-EV snapshot at 122.411 MW active-area demand. Reduced minimum voltage is 0.957434 pu versus detailed 0.981538 pu: a 0.024105-pu discrepancy. Reduced losses are 2,102.58 kW versus 1,162.97 kW, about 81% higher. This is significant near a 0.95-pu threshold. It demonstrates approximation error, not validated conservatism across locations, EV patterns and operating conditions. No broad strategy-ranking/hosting-threshold fidelity claim follows from this single snapshot.

## Required boundaries and next validation steps

For today's playground, label outcomes “constraint violations in the retained synthetic MV model.” Do not label every demand block a physical distribution transformer, every threshold crossing an outage, or a passing case a real network-safe fleet size.

To test neighborhood transformer hypotheses, add explicit representative 20/0.4- and 10/0.4-kV transformer groups with recorded rating/impedance assumptions and EV allocations per group. Actual individual-transformer conclusions require actual mappings and ratings. LV voltage or phase hypotheses additionally require appropriate LV feeder/phase representation.

Before claiming real primary capacity, verify voltage sections, individual banks, operating topology, time-aligned measured P/Q, availability and permitted loading against asset/operator data. Before claiming reduced-model capacity fidelity, compare multiple seasons, stressed locations and charging strategies against the detailed model, reporting threshold and ranking disagreements. Even agreement between these two models would validate reduction consistency only; it would not validate their shared synthetic assumptions against the real city.
