# Baseline failures, loss accounting and car-capacity hypotheses

The user clarified on 2026-09-10 that the supplied consumption figures include losses. New experiments and benchmark suites therefore interpret those figures as grid input. The earlier ten-car run was a workflow check, not a capacity study. Its results combined an overly pessimistic feeder reduction with an incorrect consumption measurement boundary.

## Hypotheses and evidence

| Hypothesis | Test | Finding |
| --- | --- | --- |
| A kWh/MWh conversion or duplicated city load causes the failures | Integrate each generated day and sum every block each interval | Rejected for the tested profiles: January gives 120,000,000/31 kWh per day; June gives 76,000,000/30. Allocation errors are below 2e-10 kW. |
| The feeder reduction exaggerates voltage drop | Replay identical block loads through the detailed network; test branch-current equivalents independently | Supported. The old equivalent multiplied total block demand by an average complete path impedance, although individual branches carry only their downstream demand. |
| Loss-inclusive consumption is being treated as delivered load | Compare supplied baseline against external-grid power | Confirmed by the user's measurement-boundary clarification. New gross-input reconciliation solves net loads so baseline load plus modeled losses equals supplied consumption. |
| Correct accounting alone makes every winter scenario feasible | Preserve demand, capacities and voltage limits after both corrections | Not supported. Residual winter voltage and worst-winter capacity limitations remain in this synthetic network. |
| Moving baseline demand and adjusting source voltage can restore worst-winter feasibility | Explicit counterfactual with preserved daily input energy, 220 MW peak cap and source setpoint 1.04 pu | Passes the tested 33-hour zero-EV case. This is a proposed demand-response/voltage-support scenario, not an established capability of Novi Sad's real grid. |

## Reduction correction

For a radial branch e, use its downstream current fraction `f_e = P_downstream,e / P_block`. The first-order equivalent for a member path is `Z_path = sum(Z_e * f_e)`. Select the path with the largest `R_path + tan(acos(0.97))*X_path`, preserving the weakest first-order voltage at the common assumed power factor.

The alternative loss-weighted equivalent `sum(Z_e * f_e²)` was also tested. It can match aggregate losses while understating the weakest member's voltage drop. It was not adopted as the voltage screen. A single equivalent is still an approximation: within-block EV demand follows member baseline shares, cross-block feeder coupling is approximate, and exact AC losses are not guaranteed.

Independent tests include two equal parallel branches (each carries half the total load), a shared trunk with unequal branch loads, unit invariance, and an AC comparison of a hand-checkable two-branch network.

At identical **delivered-load** inputs, before the user's loss-boundary clarification:

| Day | Old reduced minimum pu | Corrected worst-path minimum pu | Detailed minimum at checked snapshots pu |
| --- | ---: | ---: | ---: |
| Normal June | 0.952264 | 0.972257 | 0.978990 |
| January | 0.903946 | 0.938332 | 0.945572 |
| January +20% | 0.872076 | 0.916453 | 0.924230 |
| June +20% | 0.935821 | 0.960637 | 0.967502 |

Detailed results are selected coincident-load and reduced-voltage snapshots, not full-horizon detailed certification. These comparisons change no capacities, source voltage settings or acceptance thresholds. Evidence: `artifacts/playground/baseline-diagnosis/evidence.json`; reproducible launcher: `scripts/diagnose_baseline.py`.

## Gross consumption reconciliation

New `demand.measurement = supply_including_losses` inputs are reconciled with zero EVs. For each interval, keep the block-demand proportions and iteratively solve AC power flow until external-grid power matches the metered input within 0.01 kW. Freeze that net baseline before dispatching EVs. The 90% charger efficiency applies to EV battery energy only.

Thus `actual supply = metered baseline + charger demand + incremental network losses`, within numerical tolerance. Baseline losses are already inside the metered baseline. The model estimates its represented MV losses; unmodelled downstream losses remain inside aggregate demand rather than introducing an unsupported additional loss percentage.

Results expose both supply and load peaks, total modeled loss energy, baseline reconciliation error, and incremental EV supply energy. Controllers observe the reconciled net loads used by their capacity constraints. Gross reconciliation is independent of the EV strategy, and cached calculations require an identical network and allocation.

The `load` option remains available for inputs that explicitly exclude losses. Saved definitions and suites without the new measurement field retain their legacy load interpretation. New seasonal GUI presets and fresh benchmarks use the user's gross-input interpretation. The low-resolution consumption table has **not** been used to invent exact monthly values: the previously specified 120,000/76,000 MWh presets remain unchanged.

## Capacity-image interpretation

The capacity image labels 1,178 MW as installed network capacity and separately totals transmission, distribution and transformers. Those successive infrastructure layers cannot be summed into simultaneous customer-serving power. Its wording does not independently establish a loss-adjusted net capacity at every layer.

Existing full ratings, usable reserve, and the 0.5 baseline / 1.0 EV downstream shares are retained. There is no second percentage loss derating of the 120/150/430 MW capacity budgets. AC supply losses are counted at the transmission boundary; downstream constraints use their allocated load. The 0.5 downstream baseline share is an assumption, not measured from either image.

## Proposed winter remedies, tested separately

All cases below use the corrected reduction and loss-inclusive worst-winter consumption. None changes the operational defaults.

| Counterfactual | Minimum voltage pu | Maximum line loading % | Maximum aggregate loading % | Verdict |
| --- | ---: | ---: | ---: | --- |
| Source voltage 1.04 pu only | 0.942363 | 105.987 | 109.810 | Fail |
| Baseline downstream share 0.4 only | 0.919303 | 108.561 | 87.780 | Fail |
| Shift demand to cap grid input at 200 MW | 0.949688 | 79.547 | 82.092 | Fail |
| Source voltage 1.04 pu and 220 MW input cap | 0.963404 | 85.932 | 90.191 | Pass |

The joint case shifts 200.672 MWh from peak hours, about 4.32% of the 4,645.161 MWh daily gross input, into lower-demand hours. Daily input energy is conserved; it is not load shedding. Maximum modeled voltage is 1.04 pu. Source-voltage availability and the flexibility of that much baseline consumption require external evidence before using this as an operational recommendation. This is a baseline feasibility hypothesis; EV hosting capacity under that intervention remains a separate experiment.

Evidence: `artifacts/playground/baseline-interventions/evidence.json`; launcher: `scripts/test_baseline_interventions.py`.

A separate normal-winter test changes only source voltage from 1.02 to 1.03 pu. It passes the 33-hour zero-car case with minimum voltage 0.951287 pu, maximum line loading 87.7402%, maximum transformer loading 80.8754%, and unchanged consumption/capacity limits. This isolates voltage support as a plausible remedy for ordinary winter, while worst winter needs additional measures. Evidence: `artifacts/playground/winter-voltage-hypothesis/evidence.json`.

## Fresh tests and capacity reporting

The user subsequently selected a **Voltage-regulated grid** operating scenario. It applies the tested 1.04 pu source setting and energy-preserving 220 MW baseline peak shift to each complete day before departure-tail slicing. Summer profiles below that peak remain unchanged. The operating mode and parameters are visible in the GUI and frozen into each saved suite/network. Original operating assumptions remain an explicit alternative; no voltage, loading or energy-delivery acceptance threshold changes.

The current visible testing set uses that regulated mode: five experiment definitions with zero/500-car baseline comparisons and a 500/2,000-car charging comparison, plus a 500-car reference benchmark searching to 5,000. The earlier as-supplied capacity study was cancelled to prioritize this user-selected operating scenario; its partial evidence is not a completed maximum-capacity result.

The five experiment categories are normal summer baseline, winter baseline, worst winter, worst summer, and charging comparison. All use the gross-input boundary, seed 41001, full departure coverage, and Immediate/Capacity-aware/MPC. They retain failed grid assertions rather than weakening limits.

The benchmark retains the full coarse ladder, then measures the uppermost observed pass/fail transition down to adjacent integers. Reporting `N passed; N+1 failed` describes a measured local boundary. It does not certify unsampled gaps or prove controller feasibility is globally monotone. Ceiling-reaching and incomplete results remain bounds or unknowns.

The GUI now distinguishes zero-car baseline failures, names violation types, shows the next tested failing fleet, and identifies ten-car verification runs. Older experiments and benchmark outputs were moved outside the runtime catalog at the user's request after permanent filesystem deletion was blocked by automatic approval review. They remain recoverable under `artifacts/playground/retired-before-loss-correction-20260910`.

## Research context

The reduction audit follows branch-current accounting and explicitly separates voltage and loss preservation. See [Todorovski, A Reduction Method for Radial Distribution Feeders: Ensuring Parity in Voltages and Losses (2024)](https://todorovski-m.github.io/papers-web/papers/todorovski-2024/), DOI 10.1109/TPWRS.2024.3351490. This implementation is a first-order engineering correction, not a claimed reproduction of that paper's exact reduction algorithm.
