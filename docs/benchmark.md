# Standard ten-test EV benchmark

Open **Benchmarks** in the playground GUI. Freeze a suite once, select algorithms, and run it. Reuse that suite when adding an algorithm or revising its implementation. The catalog uses the strategy registry, so newly registered controllers appear without a second benchmark implementation.

## The ten tests

| Test | Fleet and demand |
| --- | --- |
| Shared passing fleet | Largest tested count up to the reference fleet that all selected algorithms serve safely on a normal day |
| Winter, fixed fleet | Reference fleet with January demand |
| Worst winter, fixed fleet | Reference fleet with January demand increased 20% |
| Worst summer, fixed fleet | Reference fleet with June demand increased 20% |
| Synchronized arrivals | Reference fleet arriving together at 18:00 |
| One district, fixed fleet | Reference fleet concentrated in the frozen district |
| Citywide capacity, normal | Increasing fleet ladder distributed across the city |
| Citywide capacity, worst | Same ladder with January demand increased 20% |
| District capacity, normal | Increasing fleet ladder concentrated in one district |
| District capacity, worst | Concentrated ladder with January demand increased 20% |

Defaults are a 100-car reference, 10,000-car ceiling and three held-out seeds. Automatic district selection chooses the highest normal baseline demand/capacity ratio and freezes that choice. A user-selected district is also supported.

## What makes comparisons consistent

Each suite stores the network, demand profiles, district allocation, limits, capacity assumptions and deterministic session pools. Hashes detect changed fixtures. Larger fleets extend the same session prefix; every algorithm receives identical demand and sessions for a given scenario, count and seed. Runs record code fingerprints, settings and the frozen RL policy when applicable. A code change during execution invalidates completion.

Every trial uses the shared simulator for 132 quarter-hour intervals, through the next morning's departures. Synthetic residential sessions request 14 kWh at 7.4 kW with 90% efficiency; ordinary arrivals range from 17:00 to 21:00, with departure at 09:00. These are controlled stress scenarios, not calibrated forecasts of Novi Sad travel or statistically established worst days. January and June profiles use 120,000 and 76,000 MWh monthly demand respectively.

New suites interpret these consumption inputs as supply including losses, following the user's clarification. Baseline net loads are reconciled against AC supply within 0.01 kW before adding EVs. Historical suites without `demand_measurement` keep their original load-side interpretation. Both supply and load peaks and the reconciliation error are reported. See [baseline and loss diagnosis](baseline-loss-diagnosis.md).

**Voltage-regulated grid** is a selectable operating scenario: source voltage 1.04 pu and baseline peak shifting to 220 MW while preserving daily input energy. The original operating assumptions remain available. Settings are shown beside the frozen suite and saved results. Runtime includes baseline reconciliation when its cache is cold; it is not an isolated controller-speed comparison.

A trial passes only if the full horizon completes, power flow converges, all modeled limits hold, and requested energy is delivered by departure. Every seed must pass. Delivering all energy with a voltage violation is a failure. An exception, timeout or unfinished trial is unknown, never a zero-capacity result. The GUI shows the worst seed's metrics, including shortfall, voltage, line/transformer loading, minimum grid and district headroom, runtime and control interventions.

“Spare capacity” means remaining modeled electrical headroom; it does not count parking spaces or available physical charger sockets. Minimum headroom can be negative. The common-fleet test makes this comparison at the same successfully served fleet across the selected cohort; changing that cohort can change the common count.

Capacity tests scan zero, one, the reference fleet, successive doublings and the ceiling. They continue after failures: controller performance need not be monotone in fleet size. The reported count is the largest **passing tested** count, not an exact maximum. “Ceiling reached” is a lower bound; increase the ceiling in a new suite to investigate further. Zero-car failures are exposed as baseline limitations when no tested fleet passes. Intermediate counts are not certified.

The current implementation additionally refines the uppermost observed passing/failing bracket to adjacent integer car counts. `next_failed_fleet` reports the next measured failing count above the best pass; this is a local boundary, not proof that unsampled ranges contain no other feasible count. Errors stop refinement and retain unknown status. Each fixed-fleet row also includes a zero-car control, and the GUI names voltage, asset-loading, and aggregate-capacity failures separately.

Saved comparisons group only completed jobs on the same frozen suite, keeping implementation/settings versions separate. They exclude the cohort-dependent common-fleet row. Incomplete jobs remain available for inspection. Frozen RL models must use seeds disjoint from their training seeds; RL evaluation enables its safety shield and imposes no daily energy budget. Controller fallbacks and intervention counts remain visible rather than being interpreted as unassisted performance.

## Execution and evidence

The GUI provides progress, cancellation, saved jobs, a ten-row matrix, capacity charts, detailed trial history and JSON export. Benchmark workers share the experiment/training worker lock. Runtime limits are checked between intervals; a slow interval may extend the nominal limit. A case error does not prevent other algorithms from being evaluated.

MCP tools: `ev_get_benchmark_catalog`, `ev_create_benchmark`, `ev_start_benchmark`, `ev_get_benchmark`, `ev_cancel_benchmark`, and `ev_compare_benchmark`. HTTP routes use `/api/benchmarks`, `/api/benchmarks/suites`, and `/api/benchmarks/jobs`.

Run `python -m unittest discover -s tests -v` for regression checks. `scripts/verify_benchmark.py` exercises all ten tests with three real controllers and a deliberately small ten-car ceiling, checks matching replay hashes and cancellation, and writes `artifacts/playground/evidence/benchmark_verification.json`. This bounded workflow check is not a maximum-capacity study. `scripts/verify_benchmark_gui.cjs` checks navigation, all ten rows, nine registered algorithms, saved selection, detail metrics, comparisons and mobile overflow.

## Verified baseline — 2026-09-10

All 165 repository tests passed, along with the frontend build and fresh discovery of all six MCP tools. Real run `bench-33905f6834a84fac` completed 30 cells (ten tests across immediate, capacity-aware and MPC) in 658.9 seconds on suite `suite-a70a9acd52423153f61e`, seed 41001, reference/ceiling ten cars. Replay hashes matched across controllers and actual cancellation passed.

All three controllers passed the ten-car shared-fleet, synchronized and district tests. Normal city and district searches reached the ten-car ceiling. Winter, worst winter and worst summer fixed-fleet tests failed grid limits despite full energy delivery. Both worst-day capacity searches were baseline-limited, including zero-car failures. This supports the workflow and its honest failure reporting, not an algorithm ranking or city capacity estimate. The browser check also confirmed three excluded network sources and 100% retained demand.

Quantitative matrix cards show the actual passing tested count without an inequality prefix, explicitly state when the maximum has not been found, and show zero-car minimum voltage / line loading plus minimum stage capacity margin or overload in MW. Adjacent failing tested counts remain visible. Verified with the production web build and desktop/mobile benchmark workflow on 2026-09-10.

Doubling mode freezes a zero-car control followed by powers of two starting at 2. Each capacity row stops at its first failed or unknown trial, retains all attempts and first_failed_doubling, and does not apply integer refinement. A non-power ceiling uses the highest power of two below it; reaching that bound is not a maximum. Fresh regulated run: bench-9b179943271740b0, suite-3e709edbb01b3c69755e, ceiling 32768, seed 41001, three strategies. Earlier 5000-ceiling run was cancelled when the user selected this replacement protocol.

Uncapped hosting-capacity workflow (2026-09-10): until_failure=true uses a lazy 0,2,4,8,... sequence with no fleet maximum. New larger session pools are reproduced from the frozen blocks, district and per-vehicle seed mechanism, with each trial retaining its replay hash. The first failed doubling is preserved before local integer refinement. Nonconvergence is incomplete electrical evidence, never a measured grid failure. Per-case and total wall-clock budgets remain resource safeguards and cannot establish a capacity boundary. Original capped suites retain their protocol.

Engineering reference: NREL, EV Hosting Capacity Analysis on Distribution Grids (2021), https://www.nrel.gov/docs/fy21osti/75639.pdf: incremental EV loading assessed against voltage and thermal criteria. Doubling plus local integer refinement is our numerical search choice, not a mandated industry standard. The synthetic model, source-voltage support and baseline demand shifting remain explicit assumptions; this is not utility certification.

## Charging schedule controls

Experiments now expose **Home only** and **Whole day** in Vehicles. Whole-day home/workplace/public shares use linked sliders that keep their total at100%. Benchmark setup freezes either schedule across the ten standard tests. See [whole-day charging](whole-day-charging.md) for timing, compatibility and reproducibility.
