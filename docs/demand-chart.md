# Demand chart and interval audit

The Results summary shows baseline and total city load in MW, with EV charging
in a separate aligned kW chart. Both charts start at zero and follow the selected
15-minute interval. Their vertical scales differ; curve heights must not be
compared across panels. Total load equals baseline plus EV and excludes network
losses. The dashed baseline remains distinguishable when total nearly overlaps it.

The screenshot audit on 2026-09-11 matched `run-acb9643529ac47f1`, `case-0000`
(immediate, seed 41001, 100 vehicles). At step 90 / 22:30:

- Baseline: 127,966.4214 kW; EV: 97.8667 kW; total: 128,064.2881 kW.
- 15 charging + 70 completed + 0 waiting = 85 connected; 15 had departed.
- Twelve vehicles draw 7.4 kW and three draw 3.0222 kW while finishing their
  requested energy during this interval. Charging takes precedence over completed
  for a vehicle drawing power during the interval.
- Completed refers to the requested session energy, not necessarily a full battery.
- Departed shortfall is cumulative through the interval end.

All 132 intervals reconcile city and block power totals, vehicle power allocations,
and connected-state partitions within 1e-6 kW where applicable. The run delivers
1,400 kWh against 1,400 kWh requested; its EV input is 1,555.5556 kWh at 90%
charging efficiency. Unmet and pending energy are zero, with no recorded voltage,
line, transformer, district or aggregate capacity violations. This is an arithmetic
and saved-evidence check of a synthetic scenario, not utility measurement validation.

Generated evidence: `artifacts/playground/evidence/demand-chart-audit.json`.
Frontend validation: `npm --prefix web run build` and browser inspection of the
matching 22:30 interval on the local app. Regression log:
`artifacts/playground/demand-chart-tests.log`.
