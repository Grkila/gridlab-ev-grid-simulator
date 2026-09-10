# Whole-city capacity model aligned to the 2025 image

Six sources retain all 2,648 city demand members. NS1, NS6 and FUT supplies and hubs are removed. The reduced MV network has 76 buses, 58 lines, 12 transformer equivalents, 42 demand blocks and 10 charging hubs.

The user-supplied image reports **1,178 MW**: 430 MW transmission + 598 MW distribution + 150 MW transformers. Distribution comprises 299 MW at 20 kV, 179 MW at 10 kV and 120 MW at 0.4 kV. The sum describes infrastructure across successive stages, not one simultaneous supply limit.

| Stage | Full usable rating | Reserve starts at | Applied to |
| --- | ---: | ---: | --- |
| Transmission | 430 MW | 322.5 MW | Total source power, including modelled AC losses |
| 20 kV delivery | 299 MW | 224.25 MW | Demand supplied through 20 kV delivery stations |
| 10 kV delivery | 179 MW | 134.25 MW | Demand supplied through 10 kV delivery stations |
| Downstream transformer aggregate | 150 MW | 112.5 MW | The assumed LV share of demand |
| 0.4 kV network | 120 MW | 90 MW | The same LV share after transformation |

**The last 25% is usable reserve, as clarified by the user.** Crossing 75% reports reserve use; only crossing 100% is a capacity violation. The image's approximately 295 MW reserve is 25% of the infrastructure sum (294.5 MW rounded); it is not additional supply. Default district budgets now use their full aligned ratings and total 478 MW. The earlier 80% planning restriction is superseded.

## Interpretation and assumptions

The image supplies aggregate estimates, not an asset inventory. Its transcription is preserved in `data/novi_sad/reference/inputs/capacity_estimate_2025.json`. That file also preserves the initial interpretation; the current generated `capacity_alignment.operating_model` and this document supersede its former reference-only and 80% policy fields. Its underlying publication has not been independently verified.

MV delivery-equivalent ratings are allocated by original station-MVA proportions at power factor 0.97. Transformer percent impedance is adjusted with its MVA base to preserve physical series impedance. Feeder ratings and impedances, and the original 110/35-kV transformer ratings, remain independent constraints.

For this scenario, the image's unspecified 150 MW transformer figure is assigned to an aggregate downstream MV/LV stage. This is an explicit interpretation, not a verified voltage split. Transmission and LV constraints are aggregate kW checks, not additional AC assets. They do not calculate LV voltages, phase imbalance or individual neighborhood-transformer overloads.

`network_capacity.lv_baseline_fraction` defaults to 0.5 and `lv_ev_fraction` to 1.0. These editable study assumptions assign half of baseline demand and all EV charging to both downstream stages. The image gives no measured LV demand share. Both fractions are frozen in each experiment, validated in [0,1], and must match for paired controller comparisons. The remaining demand is treated as direct MV demand. All demand is counted exactly once in the MV power flow.

Reserve use is `max(0, min(demand, rating) - 0.75 * rating)`. Headroom is `rating - demand`; it becomes negative during an overload. Unmanaged strategies can produce a counterexample; the normal stop rule saves the first violating interval. The capacity-aware strategy budgets charging against all affected stages and then checks AC losses and constraints. Baseline overload is never hidden by removing baseline demand.

The original detailed reference file is preserved. Explicit detailed checks apply the same MV calibration in memory. Historical results retain their own frozen model and never acquire new downstream verdicts. New result intervals include `capacity_layers`, and metrics include `max_network_capacity_loading_percent` and `network_capacity_overload_steps`. Unknown transmission power on non-convergence cannot pass these electrical assertions.

## Reproduction

Run `scripts/build_playground_network.py`, then `scripts/verify_capacity_alignment.py` and `python -m unittest discover -s tests -v` using the repository virtual environment. The verification script regenerates `artifacts/playground/evidence/model_validation.json` with a full-day 150 MW baseline and a detailed MV snapshot. The GUI production build uses `npm --prefix web run build`.

NS1, NS6 and FUT supplies and hubs are excluded. Their 492 demand members (39.517377 MW at the reference demand) are reassigned to retained 20-kV source feeder branches. Total city demand remains unchanged. The current app is served on port 8520.

Final acceptance on 2026-09-10: all 61 unittest checks passed after hub removal; the full-day 150 MW power-flow check converged without voltage, thermal, district or aggregate-stage violations. The production React build passed. Browser verification confirmed the 1,178 MW breakdown, usable-reserve wording, full district ratings, LV-share inputs and retained ordinary demand in the three hubless districts. The stdio MCP lifecycle passed during the layered-capacity extension.

## Supply removal and demand rebalancing

The user clarified that the three supply stations must also disappear from the map. Removed-source feeder branches are assigned largest-first to the remaining 20-kV source with the lowest projected demand/original-MVA ratio. All 2,648 member IDs remain exactly once. This deterministic reassignment changes the inferred supply connections while keeping the original feeder impedance equivalents; it does not claim measured replacement cable routes. The shared preparation is applied to both reduction and detailed diagnostic replay.

The image's 299 MW of 20-kV capacity is now allocated across NS5, NS7, NS9 and RIM at 74.75 MW each. The six 10-kV delivery groups still total 179 MW. Aggregate transmission/downstream capacities, city demand and usable reserve are unchanged. The reference demand allocation is NS2 22.419 MW, NS4 35.051 MW, NS5 38.854 MW, NS7 37.584 MW, NS9 40.521 MW and RIM 40.424 MW. This is a hypothetical rebalance, not utility validation.

The map API cache now follows the generated file revision, so Refresh picks up rebuilt topology. Historical run maps continue to show their own frozen topology and should not be mistaken for the current Network view.
