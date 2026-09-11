# Independent critical review

Status: **ACCEPTED AS A CONDITIONAL CHALLENGE STUDY**.

Reviewed final PDF SHA-256: `fcaa7381c27a56796ba34bb27533e5351fa4df178ecb31d039e20e01bae528aa`.

The reviewer inspected the simulator, demand generator, capacity layers, cohort aggregation, controllers, standalone study runner, admission estimator, analytical relaxation and report generator. This review used local code and files, without MCP services or RL execution. No operational deployment or real-city capacity is certified.

## Assessment

The revised work answers the five challenge questions as a conditional synthetic-network study. It is much stronger than a dashboard demonstration: the primary baseline is unchanged, departure energy is checked, location and timing are distinguished, and simultaneous full-power charging is separated from daily participation.

The honest conclusion is narrower than an exact maximum for Novi Sad. The monthly input table does not supply measured load shapes or a verified asset inventory. The synthetic winter baseline fails adopted limits. Positive June results therefore cannot establish a year-round real-city hosting limit.

## Findings that required correction

- Package hashes alone did not freeze study logic. Run IDs now bind a runner hash, with source snapshots.
- Static AC outputs needed explicit finite-value checks to prevent false passes.
- Search ceilings needed measured upper checks. Failed, unknown and ceiling outcomes are now distinct.
- Input validation now rejects unknown nodes, invalid placement weights and negative/nonfinite committed charging.
- Snapshot screening and capacity-aware scheduling have different allocation restrictions. The report now discloses that difference, including the assumed 1 MW public-hub scheduling budget.
- Gross supply and reconciled net node demand needed distinct definitions in the energy upper-bound formula.
- Lower peak demand is not accepted as an improvement when battery service or grid constraints fail.

## Scientific limits retained in the report

1. The three-seed fleet boundaries are local tested policy results, not global optima or statistical confidence limits.
2. The aggregate LV energy relaxation is a necessary upper bound. It ignores individual arrival windows and electrical constraints; it is not an achievable fleet estimate.
3. The public controller's 1 MW hub cap is an assumed scheduling restriction. Its comparison with uncapped immediate charging cannot establish intrinsic policy inferiority.
4. Detailed-network replays check selected snapshots within another synthetic model. They do not validate the shared physical assumptions or certify an entire charging horizon.
5. The reduced network is not uniformly conservative: detailed line loading can exceed reduced loading. Near-limit results require care even when selected voltage results improve.
6. Instantaneous admissible kW does not guarantee departure energy. Charger equivalents are allocation-dependent and do not measure merely plugged-in vehicles.
7. N-1 security, physical sockets, individual LV feeders, phase imbalance, protection and measured customer behavior are outside this study.

## Final evidence checked

The completed independent checker reports **PASS**, with no errors, missing evidence or warnings: 487 current-revision runs and 43 fixtures. The run outcomes are 246 passed, 226 failed and 15 unknown electrical results. Unknowns are not reclassified as physical capacity failures. All 59 scoped numerical regression tests passed.

Eleven independent AC evaluations agreed with saved evidence: five safe lower bounds, five failed upper bounds, and a December baseline-invalid state. All four malformed admission inputs were rejected. All 12 fleet scenario/policy groups, 204 instantaneous states, 15 integer boundaries and expected edge-case indices are complete.

The report's six paired fleet rows agree with the capacity evidence. The June home bounds are 13,000/13,500 for immediate charging and 48,000/48,500 for capacity-aware charging. The reviewer independently recomputed the necessary LV energy upper bound of 69,585 daily requests. The report does not present the gap as uncertainty or achievable extra capacity.

All 17 rendered PDF pages were reviewed in contact sheets. Dense result pages 6 and 8, the admission plot on page 11, and the detailed-replay discussion on page 16 were also inspected individually. No clipped text, broken table rows, unreadable chart labels or missing content were found. The admission plot distinguishes December baseline-invalid intervals from valid headroom states.

## Final disposition

No numerical or scientific blocking defect was found. The requested page-2 correction is complete: annual-total normalization is accurately described as tested for June and December. The rebuilt pages 2, 8 and 16 were inspected again. Clearer limiting-condition labels, comma-formatted counts and the elapsed-hour heading introduce no new layout or interpretation issue.

Reproduction instructions match the current source. The main edge stage includes both annual-total normalization cases, and capacity scans retain only the 1,000-car diagnostic after an invalid baseline.

The report is acceptable as a completed conditional challenge study. It is not an engineering certificate for real Novi Sad, nor a proof of an optimal EV fleet size. The most consequential remaining weakness is assumed network and demand data, not unfinished simulation work.

Blunt verdict: **this is now a defensible challenge submission with visible limits. Calling 48,000 the actual city's capacity would still be wrong.**
