# EV scaling diagnostic

Single synchronized 18:00 snapshot per fleet/strategy; concurrent benchmark active; reset includes cold/warm loss reconciliation; not full-day performance or capacity evidence

The grid remains 76 buses and 52 aggregate loads at all tested fleet sizes. Timings exclude reset and session generation. Capacity-aware decisions execute inside step. MPC decision time is separate; step includes power flow.

| Cars | Strategy | Decision s | Step s | AC solve s | Fallback |
|---:|---|---:|---:|---:|---|
| 128 | immediate | 0.000 | 0.075 | 0.023 | None |
| 128 | capacity_aware | 0.000 | 0.082 | 0.024 | None |
| 128 | mpc | 0.389 | 0.056 | 0.017 | None |
| 500 | immediate | 0.000 | 0.065 | 0.020 | None |
| 500 | capacity_aware | 0.000 | 0.098 | 0.025 | None |
| 500 | mpc | 0.032 | 0.079 | 0.024 | plain_least_laxity_first: variable budget exceeded |
| 4096 | immediate | 0.000 | 0.089 | 0.015 | None |
| 4096 | capacity_aware | 0.000 | 0.137 | 0.015 | None |
| 4096 | mpc | 0.295 | 0.144 | 0.021 | plain_least_laxity_first: variable budget exceeded |
| 16384 | immediate | 0.000 | 0.386 | 0.027 | None |
| 16384 | capacity_aware | 0.000 | 0.431 | 0.025 | None |
| 16384 | mpc | 0.906 | 0.240 | 0.017 | plain_least_laxity_first: variable budget exceeded |
| 65536 | immediate | 0.000 | 1.103 | 0.062 | None |
| 65536 | capacity_aware | 0.000 | 2.085 | 0.029 | None |
| 65536 | mpc | 4.037 | 1.089 | 0.022 | plain_least_laxity_first: variable budget exceeded |

This is one matched synchronized-arrival snapshot, repeated in two diagnostic executions, while a benchmark also used the host. It is not a statistically controlled throughput benchmark. The 65536-car Immediate snapshot did not converge; its AC time is not a successful solve. MPC ran its optimizer at 128 cars but fell back at 500 and above for this 60-step departure horizon. No inference that every interval of a 500-car full-day run falls back.

Conclusion: electrical aggregation already exists. At high fleet counts the dominant measured cost is vehicle allocation/state/reporting and controller projection. Cohort-based controller optimization is the meaningful next candidate; it must preserve arrival/departure, energy and charger constraints and validate against individual sessions.
