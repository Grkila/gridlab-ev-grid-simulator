# Network validity audit: transformer ratings, hierarchy and failure limits

Date: 2026-09-10. **Read-only model audit; no network changes made.** This reviewer implemented the reduction, so this is explicitly a self-review of that implementation, not independent engineering certification.

## Verdict

**The network is suitable for conditional planning experiments, but its ratings are not established as exact real-equipment failure limits. There are no 20/LV or 10/LV transformers in either the full reference model or the reduced model.** Consequently, the simulator cannot currently determine whether a particular neighborhood distribution transformer overloads or fails.

The retained source/delivery MVA values reproduce the repository's transcribed station-capacity table. This establishes implementation consistency, not correctness of the original transcription, individual unit ratings, present-day topology or protection settings. The original EDS PDF was not rechecked in this local audit. Repository provenance identifies the [EDS 2025–2034 development plan](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf), base year 2024; see `docs/data-sources-and-licenses.md:11` and `src/mvgrid/novi_sad/inferred_feeders.py:32`.

## Retained transformer inventory and provenance

Runtime inspection of `data/novi_sad/playground/reduced_network.json` returns exactly the following 12 two-winding transformer elements. Source record references below are lines in `data/novi_sad/reference/generated/novi_sad_seeded_substations.json`.

| Station | Stored source ratio | Reduced element | MVA | Source record | Qualification |
|---|---|---|---:|---|---|
| NS2 | 110/35 | 110/35 | 51.5 | line 36 | Station installed capacity represented by one equivalent element. |
| NS4 | 110/35 | 110/35 | 126 | line 49 | Station installed capacity represented by one equivalent element. |
| NS5 | 110/20/10 | 110/20 | 63 | line 62 | 10 kV winding/section omitted; table's total assigned to 20 kV equivalent. No per-winding allocation verified. |
| NS7 | 110/20 + 110/35 | 110/20 | 63 | line 88 | Uses explicit `direct_20kv_mva=63`, not total 83 MVA; separate 20 MVA 110/35 section omitted. |
| NS9 | 110/20/10 | 110/20 | 63 | line 116 | Same unverified 20/10 section simplification as NS5. |
| RIM | 110/20 | 110/20 | 63 | line 129 | Station installed capacity represented by one equivalent element. |
| LIMAN | 35/10 plus 35/20 section | 35/10 | 32 | line 157 | 20 kV section omitted; no section-specific allocation verified. |
| CENTAR | 35/10 | 35/10 | 32 | line 167 | Station installed capacity represented by one equivalent element. |
| PODBARA | 35/10 | 35/10 | 32 | line 177 | Station installed capacity represented by one equivalent element. |
| SEVER | 35/10 | 35/10 | 16 | line 187 | Station installed capacity represented by one equivalent element. |
| IND | 35/10 plus 35/20 section | 35/10 | 32 | line 197 | 20 kV section omitted; no section-specific allocation verified. |
| TELEP | 35/10 | 35/10 | 16 | line 207 | Station installed capacity represented by one equivalent element. |

The construction follows `src/mvgrid/novi_sad/model.py:177` for direct 20 kV ratings, `model.py:186` for 110/35 kV, and `model.py:217` for 35/10 kV. The reducer copies reference MVA and electrical transformer parameters at `src/mvgrid/novi_sad/playground/network.py:42`; it does not independently recover equipment nameplates.

NS1, NS6 and FUT are excluded by user instruction at `network.py:22`. This is a study boundary, not evidence that these stations do not contribute to real Novi Sad supply. Only NS5, NS7 and RIM coordinates are name-confirmed in OSM according to the source file's warning at line 3. Named location verification does not validate electrical ratings or feeder connections.

The reference documents CENTAR→NS2 and LIMAN→NS4 associations; other legacy associations are inferred (`inferred_feeders.py:84`). The reduction preserves those existing synthetic associations and all retained station transformers, but cannot make their inferred predecessors factual.

## What is absent below MV

Inspection reports bus nominal voltages **10, 20, 35 and 110 kV only**. Reduced loads attach at 10 kV (32 loads) or 20 kV (21 loads). No 0.4 kV buses, MV/LV transformers, LV feeders, individual phase loading or service connections exist.

The misleadingly named `novi_sad_synthetic_transformers.csv` contains generated demand points, not a verified transformer inventory: columns include annual energy and peak demand but no nameplate kVA, winding voltage, impedance or protection fields. `src/mvgrid/novi_sad/synthetic_transformers.py:78` generates points from land-use weights, and line 97 derives peak demand from annual energy. `src/mvgrid/novi_sad/model.py:362` turns those points into `pp.create_load` elements, not transformers. Reduced blocks do the same at `playground/network.py:104`.

**A map label or demand-point count must therefore not be presented as a count of modeled 20/0.4 kV transformers.** Public hubs are likewise loads behind an illustrative equivalent feeder with an assumed 1 MW limit; no hub supply transformer is represented (`network.py:101`).

## Assumed electrical parameters and aggregation effects

All retained transformers inherit generic `vk_percent=12`, `vkr_percent=0.45`, `i0_percent=0.10`, zero phase shift and `pfe_kw=max(18, sn_mva*0.65)` from `model.py:45`. Those values are explicitly labeled generic planning assumptions at line 54. Individual unit impedances, tap positions, vector groups, parallel unit availability, bus sections and N-1 limits are not recovered. One station-equivalent transformer cannot expose one overloaded individual unit behind an otherwise acceptable station total.

Reference cables use generic R=0.206 and X=0.115 ohm/km, 250 nF/km and 0.319 kA, with at least two parallel circuits sized using the synthetic demand and a 72% design-loading target (`model.py:60`, `model.py:312`). These are designed proxy capacities, not verified installed ampacities. Capacity-balanced routing also uses a chosen 86% margin (`inferred_feeders.py:28`), so a passing baseline is partly constructed, not independent validation.

The reduced feeder uses demand-weighted path R/X (`network.py:97`) and a minimum path capacity divided by the block's downstream baseline share (`network.py:101`). It replaces that path with a one-kilometre equivalent carrying the aggregate load and omits shunt capacitance. Shared feeder segments can belong to multiple block paths; their joint loading is not retained as a distinct shared MV feeder constraint. The approximation can both change voltage/losses and hide a common downstream bottleneck. The preserved primary and delivery transformers still enforce shared station loading, but do not substitute for omitted shared cables.

The recorded selected comparison illustrates the discrepancy: at 122.411 MW retained demand, reduced minimum voltage is 0.95743 pu versus detailed 0.98154 pu, transformer maxima 61.66% versus 60.10%, and losses 2.103 MW versus 1.163 MW. This single test does not establish conservatism in other scenarios; see `artifacts/playground/evidence/model_validation.json`.

## What a failure means in this implementation

`playground/simulation.py:87` defaults to 0.95–1.05 pu and 100% loading. At line 141 it compares every calculated bus/line/transformer value with configured bounds. At line 170 the first remaining violation or non-convergence stops the experiment when enabled.

This implements a **configured limit violation**, not a physical failure or relay trip. There is no hot-spot/oil-temperature state, ambient-temperature dependence, duration-dependent overload curve, fuse/relay characteristic, breaker operation, outage redistribution or protection coordination. The 15-minute steady-state solver also cannot detect a shorter event simply from interval-average demand.

Source and delivery kW budgets use MVA × assumed power factor 0.97, while the final AC solve evaluates actual modeled loading. MVA is not interchangeable with MW. Even a correctly transcribed nameplate is not, by itself, an exact permissible loading duration or trip threshold.

## Consequences and recommended next decisions

1. Continue describing current output as modeled MV voltage/thermal-limit violations. Do not claim actual equipment failure, LV transformer hosting capacity or operational city limits.
2. If MV/LV transformer constraints are an intended hypothesis, add an explicit representative 20/0.4 or 10/0.4 kV transformer below each relevant block/hub, with a declared count of parallel units and nameplate assumptions. If actual data are unavailable, use sensitivity cases rather than claiming exact ratings.
3. For source/delivery accuracy, verify the EDS transcription against specific pages and acquire unit counts, per-winding ratings, section connections, tap/impedance data and current switching state. Resolve NS5/NS9 and LIMAN/IND section allocation before assigning total station capacity to one winding.
4. If physical failure timing matters, choose an explicit thermal/protection model and obtain its necessary inputs. A configurable 100% stop remains acceptable for a pedagogical constraint demonstration, provided the label is honest.
5. Before stronger claims, compare multiple normal and adversarial placements against a corrected detailed reference; the current detailed reference also lacks MV/LV equipment and therefore cannot validate that omitted level.

No model edits were made during this audit. Earlier MVP software acceptance concerned implementation workflows and reproducibility; it was not acceptance of utility-equipment accuracy.
