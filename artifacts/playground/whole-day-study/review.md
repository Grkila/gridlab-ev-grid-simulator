# Independent review: charging profiles and whole-day benchmark

Status: **IMPLEMENTATION REVIEW PASSED; BENCHMARK STOPPED AT USER REQUEST**.

This review inspected the new visit generator, experiment schema and routing, district validation, benchmark fixture/version handling, charging-mix slider helper and its form integration. Package source was not edited during the running benchmark.

## Findings and fixes

- Home-only experiments could hide an invalid location-share total after switching from the mixed profile. The form now repairs an invalid total when the profile changes; sliders maintain a valid total during normal editing.
- Uncapped expansion could otherwise regenerate a saved whole-day suite with a changed profile implementation. Saved profile versions are now checked, and expanded pools must retain the exact frozen prefix. Historical home-only suites keep their original generator.
- Profile descriptions now use readable spacing and distinguish one daily visit per vehicle from a multistop travel model.

## Correctness checks

Seven independent offline tests passed. They verify nested fleets, invariance to block order, 7,000 multiday visits without overlap, complete departure-tail coverage, isolated charger-window feasibility, all 96 possible public arrival slots, location-specific synchronized starts, district isolation, and deterministic missing-public-site rejection.

The whole-day one-day benchmark fits its 132 intervals: home visits end at next-day 09:00; late public visits finish earlier. Multiday experiment profiles preserve public dwell time when avoiding overlap, and the worker extends demand through the last departure. No pending departure is intentionally dropped.

Charging profile, version and generated pool are included in the frozen suite identity. The new Python module participates in implementation fingerprints. Expanded fleets preserve their frozen prefix. Old experiment definitions without a profile still select the legacy generator.

The slider helper clamps the selected percentage to integer 0–100 and redistributes the remainder across the other two shares. Its returned fractions sum to one, including the edge where the other two shares previously total zero. The displayed total remains 100%; standard range inputs support keyboard interaction. Root-agent testing reports 303 slider moves plus keyboard checks.

Saved evidence confirms both 100-EV home-only and whole-day experiment demonstrations completed 132 intervals, with immediate and capacity-aware strategies each delivering 1,400 battery kWh and zero unmet energy. The saved test logs report 281 passing repository tests and 18 passing benchmark tests.

## Interpretation limits

- Whole day means a 70/20/10 expected home/work/public mix for the standard benchmark, with one visit per vehicle. Small sampled fleets need not have those exact proportions.
- Fixed and randomized 23:00-release policies are unchanged. They can fail even at small mixed fleets because daytime vehicles leave before release. Such failure indicates a policy/window mismatch, not exhausted physical network capacity. The UI discloses this.
- The 3–4-hour public stays are an explicit feasible-window assumption for the common 14-kWh request, not measured mobility data.
- Synchronized whole-day tests synchronize within each location type, not every vehicle at one hour.
- Implementation review and small experiment success do not certify the seven-strategy benchmark before it finishes.

## Benchmark disposition

The user subsequently requested an MVP and explicitly said a benchmark rerun was unnecessary. Benchmark `bench-1682223431ba4678`, suite `suite-cefacfbc402247c613cd`, is confirmed **cancelled**, with 42 of 70 rows saved. Further benchmark auditing was stopped in accordance with that instruction.

Partial saved rows are exploratory evidence only. This review does not endorse a final whole-day fleet ranking or claim that all 70 cells completed. No rerun is required to satisfy the revised user scope. The implementation review, independent profile tests, slider checks and small completed experiment demonstrations remain valid evidence for the MVP.

## Frontend/backend API review

**Verdict: accepted for the tested MVP workflows.** The route audit found matching server handlers for the frontend requests across experiments, benchmarks, strategies, chat, RL, continuous campaigns and the presentation. It also found two campaign defects: whole-day fixtures regenerated home-only sessions, and the campaign source binding omitted `charging_profiles.py`. Both are fixed. Independent offline regression tests now verify whole-day, home-only and legacy replay identity across city, district and synchronized cases, plus the generator's actual source hash in the runtime binding.

The reviewer inspected `e2e/results.json`: it records success, 84 check entries, 242 observed API responses, zero recorded errors and zero HTTP error responses. Those entries include repeated polling; they are not 84 distinct endpoints. The recorded browser workflow saves an experiment, runs its real worker, loads completed results, reloads, renames, deletes, restores and compares. Root-agent verification reports 12 vehicles, 132 intervals and 168 battery kWh, plus benchmark freezing without execution, a strategy proposal, all pages and desktop/mobile layouts. The mock UI regression and 303 slider transitions also passed.

Five additional independent tests in `tests/test_api_contract_review.py` passed. Besides the replay and binding checks, they exercise real loopback HTTP with worker services stubbed: chat payload forwarding, saved receipt recovery, cursor/history parsing, cancellation and missing records; RL request forwarding, cancellation and runtime-root rejection; and campaign preparation, resume, results and error responses. These prove transport contracts without launching external chat or training.

Acceptance is deliberately bounded. No full benchmark, RL training or external Codex chat was executed in this API round. Stubbed lifecycle checks do not establish worker learning quality, external authentication, subprocess recovery or every concurrency race. The original whole-day benchmark remains cancelled and unendorsed as a complete ranking. No unresolved blocking route mismatch remains in the inspected scope.

Completion evidence added by the root agent after review: the final full repository run passed all 286 tests in 152.6 seconds. Two older mocked session generators were updated to accept the added profile argument; all 27 affected adversarial tests also passed separately. The live app read-only check passed ten API reads, local geography JSON and presentation/app acknowledgements with zero POSTs or browser errors.
