# Aggregation validation and base runtime comparison

Matched 33-hour runs, frozen network/demand/seed41001, warm loss reconciliation. Wall timings share a host with a capacity benchmark and are indicative.

| Scenario | Cars | Controller | Base seconds | Aggregate seconds | Base / aggregate status | Peak delta kW | Voltage delta pu | Unmet delta kWh |
|---|---:|---|---:|---:|---|---:|---:|---:|
| normal | 500 | immediate | 9.21 | 8.63 | passed / passed | 0.000000 | 0.00000000 | 0.000000 |
| normal | 500 | capacity_aware | 9.09 | 9.00 | passed / passed | 0.000000 | 0.00000000 | 0.000000 |
| normal | 500 | mpc | 78.50 | 30.80 | passed / passed | -1.514888 | 0.00003750 | -0.000000 |
| normal | 4096 | immediate | 12.57 | 9.21 | passed / passed | 0.000000 | -0.00000000 | 0.000000 |
| normal | 4096 | capacity_aware | 16.23 | 9.30 | passed / passed | 0.000000 | -0.00000000 | 0.000000 |
| normal | 4096 | mpc | 35.08 | 57.47 | passed / passed | -11870.981095 | 0.00359106 | -0.000000 |
| worst | 4096 | immediate | 12.08 | 8.80 | failed / failed | 0.000000 | 0.00000000 | 0.000000 |
| worst | 4096 | capacity_aware | 16.06 | 7.61 | passed / passed | 17.192383 | -0.00132410 | 0.000000 |

Immediate agrees to floating-point precision in these cases. Capacity-aware preserves tested delivery and verdicts, but constrained scheduling can differ. MPC is not interchangeable: at4096 cars individual mode used22 fallback intervals versus zero with aggregation; the aggregate optimizer lowered peak by11.87MW but took longer. MPC was subsequently excluded by user request.

Separate150MW model check: all96 intervals converge; reduced minimum voltage0.97510195pu versus detailed0.98153828pu. Reduced/detailed line loading50.395/49.113%, transformer53.280/52.108%, losses1932.508/1558.809kW. This approximation is not real-city validation; loss difference is material for precision planning.

Full seven-controller benchmark: bench-c0c965da89ab4b2d, suite-19f52a8c3215ac54a015. Same regulated operating assumptions and aggregated-node model; original city demand was not restored. Uncapped doubling then local one-car refinement. Read live state before claiming completed capacity results.
