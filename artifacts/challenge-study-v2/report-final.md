Novi Sad: how much EV charging can this model support?

Schneider challenge | Direct simulation study | 11 September 2026

The supplied data support a conditional planning study. They do not establish a measured hosting limit for the real city. This report answers the five challenge questions using the existing calculators and AC simulator, with newly frozen inputs and completed runs. It uses no RL results.


Question | Answer supported by this study
1. Maximum fleet without upgrades | On the June reference day, 13,000 home-charging EVs pass with immediate charging and 48,000 pass with capacity-aware charging across three seeds. These are sampled daily participation bounds. Winter baseline violations prevent a year-round certification.
2. Does location matter? | Yes, through both availability hours and electrical placement. Equal-energy home, workplace, public and mixed cases are compared, with a same-node timing control. Public-hub results depend on ten assumed sites.
3. Critical simultaneous count | An allocation-specific threshold is measured for full-power 7.4, 22 and 50 kW chargers. It is distinct from the fleet served over a day and from the number of plugged-in vehicles.
4. Which charging strategy helps? | Delayed and controlled charging are compared at matched demand and energy service. A lower peak with missed departures is not accepted as a successful improvement.
5. Time-dependent algorithm | The implemented admission screen tests additional EV kW against AC voltage, thermal, district and aggregate-stage constraints every 15 minutes, then reports charger equivalents. It checks a specified placement, not an optimal allocation.

The main unresolved issue is the winter baseline. Adding a controller does not make an already-invalid baseline a valid estimate of the real network. The separate voltage-support and demand-shifting cases show what additional assumptions buy, rather than silently changing the primary answer.

1. What the handout actually supplies

The first photograph describes five tasks and calls its consumption curves fictional. Its chart supplies monthly energy, not historical hourly or quarter-hour power measurements. The second supplies estimated infrastructure totals. Neither photograph provides a verified feeder inventory, measured charging behavior or a usable hourly headroom curve. [1, 2]


Month | 2024 energy (MWh) | 2025 energy (MWh)
January | 113,883 | 116,985
February | 105,207 | 108,060
March | 100,219 | 102,944
April | 88,797 | 91,743
May | 76,792 | 79,361
June | 74,739 | 76,965
July | 78,034 | 80,282
August | 76,745 | 78,409
September | 82,901 | 84,928
October | 95,688 | 98,283
November | 106,247 | 109,459
December | 120,553 | 124,221
Sum of monthly rows | 1,119,805 | 1,151,640
Printed annual total | 1,116,804 | 1,147,635
Row sum minus printed total | 3,001 | 4,005

The discrepancy is in the supplied table; a separate reviewer checked the transcription. The simulations preserve the monthly rows. The 2025 difference is about 0.35% of the printed annual total. A sensitivity check applies the common annual-total factor 1,147,635 / 1,151,640 to June and December. It does not quietly replace the source values.

The average supply power implied by the 2025 row sum is 131.47 MW. This average is not the evening peak and cannot by itself determine EV capacity.

2. Capacity interpretation and study assumptions


Supplied estimate | How it enters the study
430 MW transmission | Aggregate source supply, including modeled AC losses.
299 MW at 20 kV; 179 MW at 10 kV | Delivery-equivalent capacities; electrical and district limits also apply.
150 MW transformers | Assigned to an aggregate downstream transformer stage. The voltage split is an explicit interpretation.
120 MW at 0.4 kV | Aggregate LV demand budget; no physical LV feeder voltages are modeled.
1,178 MW total; 25% reserve | Successive infrastructure stages are not added into one supply limit. Reserve begins at 75%; full rating remains usable.

The 430, 598 and 150 MW figures describe different stages. Subtracting city demand from their 1,178 MW sum would double-count infrastructure along the delivery path. Likewise, the approximately 295 MW reserve is 25% of that sum, not a separate block of EV supply. [2, 3]

With the same demand assigned to both downstream stages, the 120 MW LV limit binds before the 150 MW transformer aggregate. This redundancy is a consequence of the chosen interpretation. It does not establish the capacity of any individual transformer.


Assumption | Frozen choice and consequence
Network | 76 buses, 58 lines, 12 transformer equivalents, six sources, 42 demand blocks and ten illustrative public hubs. All 2,648 synthetic demand members remain after source reassignment.
Primary operation | 1.02 pu source voltage; existing adopted ratings; no non-EV demand shifting.
Demand boundary | Gross supply including losses, following prior project clarification. The photograph alone does not resolve the measurement boundary.
Downstream demand | 50% of non-EV demand and 100% of EV demand count against the LV and downstream-transformer stages. Sensitivity uses 30% and 70%.
EV service | One session per car, 14 battery kWh, 7.4 kW grid-side charger, 90% efficiency. No inferred number of actual registered EVs.
Numerics | Balanced AC power flow; 15-minute intervals; 0.95 to 1.05 pu voltage; 100% adopted loading. These are study limits.

3. How the calculations work

Each monthly energy value is divided by the actual number of calendar days, including February 2024 with 29 days. A fixed seasonal daily shape is interpolated to 96 quarter-hour values and normalized so its integral equals the monthly average day. Day two continues the baseline until the last departure at 09:00. No second-day EV arrivals are generated.

<b>Daily baseline energy:</b> E_day = 1,000 E_month / days_in_month, in kWh.<br/><b>Daily power profile:</b> P(t) = E_day s(t) / [0.25 sum s(t)], in kW.<br/><b>EV battery energy:</b> E_battery = 0.90 sum P_EV(t) x 0.25.<br/><b>Supply:</b> reconciled non-EV load + EV charging + modeled network losses.

The baseline allocation preserves city power at every interval. An iterative AC calculation then finds the non-EV node loads whose source power matches the supplied gross demand within 0.01 kW. The same reconciled loads are reused across strategies. Incremental EV losses enter the subsequent AC solution; baseline losses are not charged twice.

A passing fleet has to meet both requirements

Every interval must converge and satisfy voltage, line, transformer, district and aggregate-stage limits. Every vehicle must receive its required battery energy by departure. The report rejects a case with pending departures, missed energy, nonfinite electrical results or a numerical failure. Failed trajectories still finish the horizon so their demand and service consequences remain visible.

Home arrivals occur from 17:00 to 21:00, with departure at 09:00 the next day. Workplace arrivals occur from 08:00 to 10:00, with departure at 17:00. Public arrivals occur from 08:00 to 20:00 and stay three hours. The same 14 kWh and 7.4 kW values apply to the primary location comparison. A three-hour public stay is long enough in isolation; a separate one-hour test deliberately is not.

What the search can establish

Capacity scans test 0, 1,000, 5,000, 10,000, 20,000, 40,000 and 80,000 vehicles. Each scenario whose baseline passes uses three fixed seeds, 61001 to 61003. The search refines the largest observed passing/failing bracket to 500 cars. It does not assume that a controller is feasible at every unsampled count, and it does not prove a global optimum. Baseline-invalid scenarios retain a 1,000-car diagnostic rather than a misleading positive capacity search.

4. The baseline is the first constraint

The 2025 representative-day model violates at least one limit in January, February, November, December. These are zero-EV cases. The result is a warning about the synthetic model and its operating assumptions, not evidence that the real city cannot supply its existing consumers.


2025 month | Supply peak (MW) | Minimum voltage (pu) | Grid verdict
January | 218.44 | 0.9426 | Fails assumed limits
February | 223.39 | 0.9404 | Fails assumed limits
June | 145.41 | 0.9723 | Pass
October | 181.38 | 0.9586 | Pass
November | 208.74 | 0.9472 | Fails assumed limits
December | 231.95 | 0.9366 | Fails assumed limits

Both energy years use the same adopted 2025 network, isolating demand changes. The 2024 line is not a reconstruction of the historical 2024 grid. Each month uses one synthetic representative day, not every weather event or weekday. A seasonal average-day pass does not certify every day in that month. A +20% stress day is a defined perturbation, not a statistically established worst day.

5. Answer 1: fleet served without upgrades


Operating case / location | Immediate pass / fail | Capacity-aware pass / fail | What fails at the next count
June; existing assumptions; home | 13,000 / 13,500 | 48,000 / 48,500 | Immediate: LV aggregate. Managed: departure shortfall.
December; existing assumptions; home | Not certified | Not certified | Immediate: Baseline invalid. Managed: Baseline invalid.
December +20%; voltage + demand shift; home | 3,000 / 3,500 | 20,500 / 21,000 | Immediate: LV aggregate. Managed: departure shortfall.
June; existing assumptions; work | 10,000 / 10,500 | 27,500 / 28,000 | Immediate: LV aggregate. Managed: departure shortfall.
June; existing assumptions; public | 6,000 / 6,500 | 6,000 / 6,500 | Immediate: line overload. Managed: departure shortfall.
June; existing assumptions; TELEP | 1,000 / 1,500 | 5,000 / 5,500 | Immediate: undervoltage. Managed: departure shortfall.

Every passing count in this table meets service and grid requirements on all three seeds. The next failed count is a sampled local boundary, not an estimate of the real city to the nearest car. The coarse scan continues after ordinary failures, preserving unfavorable cases.

A separate energy-only calculation caps June home charging at 69,585 daily 14 battery-kWh requests: floor[0.90 x sum(max(0, 120,000 - 0.50 P_net(t))) x 0.25 / 14] over 17:00 to next-day 09:00. P_net is reconciled non-EV node demand in kW; 120,000 kW is the LV budget. This bound ignores other limits and individual arrival times. The gap above witnessed controller feasibility is not a confidence interval.

The fleet number means vehicles that each request 14 kWh in this modeled charging day. Converting it into the total registered EV population requires a charging-participation model. For example, dividing by an assumed daily charging fraction would only produce another conditional estimate; this report does not invent that fraction.

The regulated December +20% rows use 1.04 pu source voltage and daily baseline peak shifting to 220 MW. They belong to the intervention scenario. They cannot be used as the unqualified answer for existing operation without upgrades.

6. Answer 2: home, workplace and public charging


Placement | Policy | Supply peak (MW) | Unmet battery (kWh) | Seeds passing
Home | Immediate | 149.02 to 149.24 | 0.0 | 3/3
Home | Capacity-aware | 149.02 to 149.24 | 0.0 | 3/3
Work | Immediate | 145.41 | 0.0 | 3/3
Work | Capacity-aware | 145.41 | 0.0 | 3/3
Public | Immediate | 146.61 to 146.76 | 0.0 | 3/3
Public | Capacity-aware | 146.61 to 146.76 | 0.0 | 3/3
Mixed | Immediate | 148.18 to 148.25 | 0.0 | 3/3
Mixed | Capacity-aware | 148.18 to 148.25 | 0.0 | 3/3

Each row represents the same 1,000 vehicles and 14,000 kWh battery request. Home and workplace charging use ordinary demand blocks; public charging uses ten illustrative hubs. The mixed case uses expected shares of 70% home, 20% workplace and 10% public. The exact sample shares vary by seed.

These are joint timing-and-placement scenarios. A public-hub advantage cannot be attributed to daytime charging alone because the hubs also have different electrical connections. The timing-only control below places public-style and workplace-style sessions on the same ordinary-node distribution as home charging.

The capacity-aware controller also enforces an assumed 1 MW allocation budget per public hub. Immediate charging has no such scheduling cap; both undergo the common AC and aggregate checks. This conservative controller restriction can lower its public-site fleet bound. It is not evidence of a measured 1 MW installation or a physical socket inventory.


Timing, ordinary nodes | Policy | Supply peak (MW) | Unmet battery (kWh)
Work | Immediate | 145.41 | 0.0
Work | Capacity-aware | 145.41 | 0.0
Public | Immediate | 146.63 to 146.78 | 0.0
Public | Capacity-aware | 146.63 to 146.78 | 0.0

December location cases are retained in the evidence. Where their zero-EV baseline is invalid, moving EVs cannot establish full-day grid feasibility. Physical parking spaces, charger sockets and real hub utilization are outside the supplied data.

7. Answer 3: critical simultaneous charging

This test places actual integer vehicles at nested, seed-fixed nodes and switches all of them on at full charger power. It checks the safe count again and then the next count in a fresh AC solve. The test fixes time, location and charger rating; it does not claim that the same count applies everywhere.


Month / hour / place | Charger kW | Safe cars | Next count | Limiting condition
06 / 03:00 / city | 7.4 | 10,044 | 10,045 | LV aggregate limit
06 / 03:00 / city | 22.0 | 3,378 | 3,379 | LV aggregate limit
06 / 03:00 / city | 50.0 | 1,486 | 1,487 | LV aggregate limit
06 / 18:00 / city | 7.4 | 8,618 | 8,619 | LV aggregate limit
06 / 18:00 / city | 22.0 | 2,898 | 2,899 | LV aggregate limit
06 / 18:00 / city | 50.0 | 1,275 | 1,276 | LV aggregate limit
06 / 20:00 / city | 7.4 | 6,516 | 6,517 | LV aggregate limit
06 / 20:00 / city | 22.0 | 2,191 | 2,192 | LV aggregate limit
06 / 20:00 / city | 50.0 | 964 | 965 | LV aggregate limit
06 / 18:00 / TELEP | 7.4 | 957 | 958 | Low voltage: TELEP-F2
06 / 18:00 / TELEP | 22.0 | 319 | 320 | Low voltage: TELEP-F2
06 / 18:00 / TELEP | 50.0 | 142 | 143 | Low voltage: TELEP-F2
12 / 18:00 / city | 7.4 | Not certified | Not tested | Low voltage: LIMAN-F2
12 / 18:00 / city | 22.0 | Not certified | Not tested | Low voltage: LIMAN-F2
12 / 18:00 / city | 50.0 | Not certified | Not tested | Low voltage: LIMAN-F2

Zero admissible charging during a baseline violation means the screen refuses admission under that modeled state. It does not imply a measured zero capacity for Novi Sad. Outside such states, safe N and failed N+1 are adjacent observations for this placement. No other allocation is ruled out.

A continuously controlled cohort may give a small positive current to many cars. Counting all of them as charging would inflate the apparent simultaneous capacity. For that reason, this table uses full-power cars. The time-dependent curve on the next pages reports kW first.

8. Answer 4: strategies and energy service


Home policy, 10,000 EVs | Supply peak (MW) | Unmet battery (kWh) | Seeds passing | Fallback intervals
Immediate | 182.49 to 183.29 | 0.0 | 3/3 | 0
Start at 23:00 | 201.68 to 201.70 | 0.0 | 0/3 | 0
Random delay after 23:00 | 145.41 | 0.0 | 3/3 | 0
Capacity-aware | 182.49 to 183.29 | 0.0 | 3/3 | 0
Smoothed LLF + fallback | 182.49 to 183.29 | 0.0 | 3/3 | 0
Valley filling + protection | 153.77 to 153.87 | 0.0 | 3/3 | 0

All rows request 140,000 battery kWh. The intervals span 33 hours, so a lower peak cannot be purchased by leaving next-morning departures outside the analysis. Reported delivery in a grid-invalid interval is modeled demand accounting, not proof that electricity would physically be supplied during an outage.


Controller | Mechanism and evidence boundary
Immediate | Charge on arrival until the battery requirement is met; no automatic grid protection.
Fixed / randomized delay | Release home charging at 23:00, optionally adding a seeded delay of up to almost four hours. These policies can synchronize a new night peak.
Capacity-aware | Prioritize departure order under node/source/district/stage budgets, then halve EV power if the AC check fails. Conservative; not a peak optimizer.
Smoothed LLF | Urgency-based constrained smoothing. A bounded optimizer can fall back to plain LLF; the table reports affected intervals.
Valley filling | Causal persistence forecast, eight coordination iterations, headroom projection and the same AC protection. This is a finite-iteration implementation, not a proven optimum.

The central protection is part of the controlled solution. Improvements cannot be attributed solely to the underlying scheduling rule. There is no claim that these implementations reproduce a research paper or that RL is needed to solve the challenge.

9. Read the load curves before choosing a policy

June 2025, 10,000 home-charging vehicles, seed 61001. Every curve uses the same session list, baseline and energy request. The dashed line is the baseline without EVs. Differences across the other two seeds appear as ranges in the table.


Policy versus immediate | Paired total supply peak reduction | Eligible pairs
Start at 23:00 | No valid service-and-grid comparison | 0/3
Random delay after 23:00 | 20.32 to 20.67% | 3/3
Capacity-aware | 0.00 to 0.00% | 3/3
Smoothed LLF + fallback | 0.00 to 0.00% | 3/3
Valley filling + protection | 15.73 to 16.05% | 3/3

The total supply peak includes non-EV demand. It is different from the EV-only peak. A policy can flatten EV charging while leaving the city peak almost unchanged if the non-EV peak dominates. Negative reduction means an increase, and is retained rather than hidden.

For the tested June home-charging case, randomized overnight release is the simplest successful peak-reduction policy. A common fixed release at 23:00 creates a new peak and fails. For a more heavily loaded system, use a capacity-aware admission layer and departure checks; the unprotected random-delay policy is not generally grid-safe. The regulated winter results demonstrate that limitation. No policy is recommended as an operational deployment without measured-network validation.

10. Answer 5: an admission estimate at each instant

The screen runs at all 96 quarter-hour states for June and December. The proposed additional EV demand follows the ordinary-node baseline weights. Twelve additional district snapshots test concentrated charging. These curves contain no promise about battery energy at future departures.

At a baseline-invalid state, the algorithm returns zero admissible additional kW with the violation reason. Elsewhere, it doubles a trial power from 1 MW until it finds a failure or unknown result, then refines the local bracket to less than 1 kW. It rechecks the safe point. A numerical unknown remains unknown; a passing search ceiling is not called a maximum.

For a fixed placement, a hand-calculated upper bound is the smallest affected capacity headroom divided by that stage's share of added EV power. The implemented AC search checks reactive power, network losses and voltage as well. A single citywide subtraction cannot perform these checks.

11. Algorithm inputs, outputs and limitations


Item | Definition
Inputs | Current non-EV node loads, already committed EV kW by node, proposed placement weights, source voltage, AC topology, asset/stage/district ratings and downstream shares.
Per-vehicle conversion | For homogeneous full-power chargers: N_equivalent = floor(P_admissible / charger_kW). Integer placement is checked separately because rounding across nodes matters.
Outputs | Additional admissible kW, safe tested placement, next failed or unknown trial, limiting assets/stages, baseline validity, runtime and full-power equivalents.
Execution | Python, pandapower and NumPy using the frozen local files. Direct calls only; no MCP service and no RL policy.
Admission versus scheduling | Passing now does not guarantee enough energy before departure. A controller must also enforce availability, charger limits, remaining battery energy and later network headroom.
Connected vehicles | The maximum number merely plugged in is undefined without sockets or minimum current. This report answers actively charging power and daily energy service instead.

Measured end-to-end estimator runtime was 1.84 seconds at the median and 2.53 seconds at the slowest tested state. Simulations ran concurrently, so these values describe this study machine under load; they are not controller-only latency benchmarks.

The instantaneous screen checks AC voltage/thermal limits plus district and aggregate stages. The capacity-aware scheduler additionally uses conservative node/source allocation budgets before its AC protection. This difference is deliberate: a physically passing snapshot is not a promise that the heuristic will discover or sustain that dispatch.

Existing charging enters the same EV load vector before extra power is tested. The 1 MW committed-charging test uses the same placement and checks how remaining admission falls. The input checks reject unknown nodes, invalid placement weights and negative or nonfinite commitments. Separate operational limits, forecasts and safety margins would be required for deployment with measured data. The present algorithm is a planning demonstration.

12. Edge cases: what changes the answer


Case / changed assumption | Policy | Peak MW | Unmet kWh | Verdict
10,000 EVs; June LV baseline share 0.3 | Capacity-aware | 183.0 | 0.0 | passed
10,000 EVs; June  | Capacity-aware | 183.0 | 0.0 | passed
10,000 EVs; June LV baseline share 0.7 | Capacity-aware | 165.3 | 0.0 | passed
10,000 EVs; June charger kW 3.7 | Capacity-aware | 179.4 | 0.0 | passed
10,000 EVs; June charger kW 11 | Capacity-aware | 182.8 | 0.0 | passed
10,000 EVs; June charger kW 22 | Capacity-aware | 182.9 | 0.0 | passed
10,000 EVs; June battery kWh 7 | Capacity-aware | 164.2 | 0.0 | passed
10,000 EVs; June battery kWh 28 | Capacity-aware | 194.9 | 0.0 | passed
10,000 EVs; June battery kWh 0 | Capacity-aware | 145.4 | 0.0 | passed
5,000 EVs; June district rating multiplier 0.8, TELEP | Capacity-aware | 148.2 | 0.0 | passed
5,000 EVs; June district rating multiplier 1.2, TELEP | Capacity-aware | 148.6 | 0.0 | passed
10,000 EVs; June; existing assumptions; flat daily profile  | Capacity-aware | 144.5 | 0.0 | passed
10,000 EVs; June; existing assumptions; sharper daily peak  | Capacity-aware | 192.7 | 0.0 | passed
10,000 EVs; June (annual-total scaling); existing assumptions  | Capacity-aware | 182.5 | 0.0 | passed

LV-share, energy and charger changes are scenario sensitivities, not confidence intervals. Charger and energy probes use seed 61001; the LV-share comparison uses all three seeds. The zero-energy case checks that idle vehicles do not invent charging demand.

Daily shape matters much more than the small annual-total discrepancy in these probes. With the same monthly energy and 10,000 controlled home EVs, the flat and sharper profiles produce supply peaks of 144.5 and 192.7 MW on seed 61001. Monthly energy alone does not select between those shapes.

13. Edge cases and separate interventions


Case / changed assumption | Policy | Peak MW | Unmet kWh | Verdict
10,000 EVs; December (annual-total scaling); existing assumptions  | Capacity-aware | 231.1 | 0.0 | failed
10,000 EVs; June all arrivals at 18:00 | Immediate | 218.4 | 0.0 | failed
10,000 EVs; June all arrivals at 18:00 | Start at 23:00 | 201.7 | 0.0 | failed
10,000 EVs; June all arrivals at 18:00 | Random delay after 23:00 | 145.4 | 0.0 | passed
10,000 EVs; June all arrivals at 18:00 | Capacity-aware | 193.5 | 0.0 | passed
1,000 EVs; June public | Capacity-aware | 146.6 | 0.0 | passed
1,000 EVs; June charger kW 22, public | Capacity-aware | 146.7 | 0.0 | passed
1,000 EVs; June charger kW 50, public | Capacity-aware | 146.9 | 0.0 | passed
1,000 EVs; June public dwell in quarter-hours 4, public | Capacity-aware | 146.0 | 7,340.0 | failed
1,000 EVs; June work | Start at 23:00 | 145.4 | 14,000.0 | failed
10,000 EVs; December +20%; existing assumptions  | Capacity-aware | 278.3 | 0.0 | failed
10,000 EVs; December +20%; voltage support only  | Capacity-aware | 278.3 | 0.0 | failed
10,000 EVs; December +20%; voltage + demand shift  | Capacity-aware | 232.2 | 0.0 | passed

A one-hour stay at 7.4 kW and 90% efficiency can deliver only 6.66 battery kWh. It cannot satisfy a 14 kWh request even with an unlimited grid. The simulator must report that shortfall. Starting workplace charging at 23:00 misses a 17:00 departure; that edge case demonstrates a policy mismatch, not the merit of a different controller.

14. Headroom sensitivity and operational assumptions


Instantaneous sensitivity, June 18:00 | Additional EV MW | Baseline verdict
LV baseline share 0.3 | 86.27 | passed
LV baseline share 0.5 | 63.78 | passed
LV baseline share 0.7 | 41.29 | passed
Adopted thermal/stage/district ratings x0.8 | 39.78 | passed
Adopted thermal/stage/district ratings x1.2 | 87.78 | passed
1 MW already charging in same placement | 62.78 | passed

The combined December +20% intervention shifts 254.60 MWh of non-EV energy away from the original peaks each day, preserving daily energy. Its original peak is 278.34 MW and its imposed cap is 220 MW. Source voltage rises from 1.02 to 1.04 pu. Neither flexibility nor voltage-control availability is established by the photographs.

Combined intervention: December +20%, 10,000 home EVs


Policy | Peak (MW) | Unmet (kWh) | Seeds passing
Immediate | 257.93 to 258.49 | 0.0 | 0/3
Start at 23:00 | 292.73 to 292.76 | 0.0 | 0/3
Random delay after 23:00 | 222.53 to 223.42 | 0.0 | 0/3
Capacity-aware | 232.24 to 232.31 | 0.0 | 3/3
Smoothed LLF + fallback | 232.25 to 232.35 | 0.0 | 3/3
Valley filling + protection | 231.55 to 231.56 | 0.0 | 3/3

The invalid-input checks reject negative, nonfinite and zero gross-supply demand. Zero gross supply is outside this reconciliation model because it includes transformer no-load losses. This is an input-domain boundary, not a simulated blackout.

15. What the detailed model and reviewer found


Case | Hour from start | Reduced min pu | Detailed min pu | Difference pu
06 / 0 EVs | 20 | 0.9723 | 0.9790 | 0.0067
12 / 0 EVs | 19 | 0.9373 | 0.9445 | 0.0073
12 / 0 EVs | 20 | 0.9366 | 0.9439 | 0.0073
06 / 10000 EVs | 20 | 0.9589 | 0.9658 | 0.0069
06 / 48000 EVs | 20 | 0.9631 | 0.9706 | 0.0075
06 / 48000 EVs | 31 | 0.9513 | 0.9576 | 0.0063
06 / 13500 EVs | 19.75 | 0.9541 | 0.9610 | 0.0070
06 / 13500 EVs | 20 | 0.9526 | 0.9596 | 0.0070

These checks replay the same node demand into the larger synthetic network. They assess reduction error at selected snapshots. They do not independently validate the shared topology, asset assumptions or the real city. A disagreement near 0.95 pu is material; it must not be hidden behind agreement in total energy.

Both checked December baseline states remain below 0.95 pu in the detailed model. The selected 48,000-car snapshots pass its voltage and thermal checks, but this is not a full-horizon detailed certificate. At next-day 07:00, detailed line loading is 92.16% versus 86.38% in the reduced model, so the reduction is not uniformly conservative. The 13,500-car immediate case fails the assumed aggregate LV budget; acceptable detailed voltage does not remove that separate constraint.

The study verification covers 487 current-revision full-horizon attempts: 246 passed, 226 failed and 15 had unknown electrical evidence. There are 43 demand fixtures. All 59 scoped numerical regression tests passed. The independent checker found 0 errors after completion and rebuilt 11 selected AC states without calling the study evaluator.

The reviewer required fixes before acceptance: bind the runner itself to results, reject nonfinite static outputs, check search upper bounds, and distinguish snapshot constraints from the scheduler's conservative allocation budgets. Those findings led to code and verification changes. Earlier unbound exploratory runs are retained but excluded from the report.

The resulting evidence supports a reproducible conditional study. It still cannot support a utility-certified annual EV limit, individual LV-transformer hosting claims, outage predictions or an optimality claim. The numerical precision of an internal search does not remove those limits.

16. What should be submitted, and what should be claimed

The defensible submission is the method, the matched comparisons and the conditional results. The June fleet bounds answer the charging-service question for the adopted network. The winter baseline failure explains why the supplied data do not support an unconditional citywide number. Both belong in the conclusion.

A practical next study would first reconcile the winter baseline with measured feeder and source-voltage data, then replace aggregate LV budgets with representative or verified downstream equipment. Charging-location and participation data would convert a daily-session result into a fleet forecast. These are missing inputs, not software features that another dashboard can substitute for.

Evidence and reproduction

The accompanying evidence directory contains frozen simulator source, network files, monthly profiles, per-run inputs and hashes, complete scalar traces, capacity attempts, instantaneous probes, the independent review and numerical-test logs. Each run fixes a session hash; its runner snapshot fixes controller settings. All final claims use the current runner revision: 8a2a820e1e817201.

Reproduction from this checkout: run scripts/challenge_study.py with stages prepare, baseline, matrix, capacity and edges; run scripts/challenge_instant.py; run scripts/challenge_analytical.py; run scripts/challenge_validation.py and scripts/challenge_boundary_replay.py; run scripts/challenge_study.py verify; then run scripts/review_challenge_study.py --require-complete --ac. Finally run scripts/build_challenge_report.py. The prepare stage preserves an existing frozen input set. Package dependency versions and SHA-256 hashes are recorded in frozen/manifest.json.

Sources and evidence references

[1] User-supplied photograph: challenge statement and fictional monthly consumption table, 2024 and 2025. Monthly entries transcribed and independently checked.<br/>[2] User-supplied photograph: Procena kapaciteta elektricne mreze Novog Sada (2025). Capacity estimates and reserve graphic; underlying utility publication not independently verified.<br/>[3] Existing project model and documented assumptions: docs/capacity-alignment-2025.md, docs/baseline-loss-diagnosis.md and docs/models/novi-sad.md. Current frozen data take precedence over superseded historical descriptions.<br/>[4] New study evidence: artifacts/challenge-study-v2. This report uses newly executed direct simulations, not the invalidated historical benchmark or RL campaign.<br/>[5] OpenStreetMap-derived synthetic network: attribution to OpenStreetMap contributors, ODbL. Original model-generation project attribution remains in CONTRIBUTORS.md.

Prepared in English to match the working discussion. Numerical results are model outputs; all capacity, behavior and operating assumptions remain visible.