# Acceptance review — EV hypothesis playground

Status: **MVP ACCEPTED with the evidence boundaries below**, 2026-09-10. Source correction loops, independent backend/API testing and parent-executed production-browser workflows are complete. This review distinguishes code inspection from exercised evidence; a successful build alone is not browser acceptance.

Subsequent electrical-validity audit: **real equipment-failure and neighborhood transformer-capacity claims are rejected**. [Independent audit](network-validity-independent-audit.md) and [topology/provenance audit](network-validity-topology-audit.md) document absent MV/LV transformers, aggregate station ratings, assumed cable capacity and missing protection/thermal behavior. Software acceptance above must not be interpreted as acceptance of those physical claims.

Reviewer independence: this reviewer implemented the electrical reduction earlier, so its network findings are self-review, not an independent validation of that model. Review of the root service, worker, React UI and chat integration is separate from their implementation. The independent workflow tester verified backend/API agreement; the parent performed browser interactions. The tester could not access a browser independently and did not reproduce those UI interactions.

## Checklist

| Requirement | Status | Evidence / limitation |
|---|---|---|
| Small pandapower solve each 15-minute step | PASSED | `simulation.py`; nine focused simulation tests previously passed. |
| Electrical delivery hierarchy, retained transformer chains | PASSED (self-review) | Generated 77-bus model; 12 transformers, 59 lines, 53 load blocks; reproducible reducer. No angular clustering remains. |
| Exclude NS1, NS6, FUT without redistributing excluded city demand | PASSED | Network excludes sources; worker scales city input by 0.8160733804473949; active-source inputs bypass scaling. |
| District and every upstream transformer/line monitoring | PASSED | Simulator iterates all electrical assets and maps violations to downstream blocks; district and transformer records persist each interval. |
| First-limit stop preserves warning and partial evidence | PASSED | Worker saves stopped prefix; evaluation incomplete; partial runs cannot qualify for paired comparison. Prior regression evidence exists. |
| Seasonal generator, kWh/kW conversion, 96 steps, sensitivity | PASSED | Demand generator plus tests; explicit units and scope. |
| Winter/summer presets, +20% scenario and compounded growth | PASSED by inspection and reported final suite | Schema/generator/form preserve coordinated presets; final independent Python freeze includes demand tests. |
| Immutable experiment language and MCP JSON | PASSED | Pydantic validation, definition digests, snapshots, network/input/source fingerprints. |
| Fair replay and four strategies | PASSED | Seeded sessions reused across strategies; immediate/delay/randomized/capacity-aware implementations. Capacity-aware AC scaling is conservative, not optimal. |
| Stress ordering and conclusive early rejection | PASSED | Full chronological episodes sorted by exogenous concurrency; prefix monotonicity guard prevents invalid lower-bound rejection. |
| GA/RL extension interface | PASSED for MVP | Public reset/step and external charging actions; optimization algorithms intentionally future work. |
| Optional detailed validation + benchmark | PASSED (self-review) | `model_validation.json`; reduced 96-step benchmark and selected detailed comparison, explicit approximation errors. |
| MCP actual protocol lifecycle | PASSED | Final actual stdio lifecycle tests cover all ten tools; final engine fingerprint independently matches current source and inputs. |
| Plugin manifest + workflow skill | PASSED by inspection | Local manifest, MCP config and skill exist; configurator rewrites checkout-specific paths. Installation in a fresh Codex client remains unverified. |
| Notebook runnable top-to-bottom | PASSED | Initialization corrected; evidence/notebook.json records top-to-bottom execution in 9.15 seconds with expected stopped status. |
| React green GUI build/layout | PASSED on parent browser evidence | Final compiled UI exercised with actual CUA DOM and screenshots; independent tester had no browser access. |
| OSM and actual reduced electrical edge connectivity | PASSED by inspection | React draws hierarchy edge endpoints on OSM; line geometry explicitly approximate. |
| Cars connected to blocks in results | PASSED | Parent verified car connections and NS5-F1 popup at 19:30; independent API check agrees with 21 connected cars in that block. |
| Correct transformer time-series visualization | PASSED by reinspection | Pivoted to one row per step and one series per transformer. |
| HH:MM across all charts and heatmap | PASSED by reinspection | Derived full-horizon ticks and visible heatmap clock axis now present. |
| Null/non-convergence represented as unknown | PASSED by reinspection | Null formatting, gray heatmap/map and disconnected unknown chart intervals now implemented. |
| Vehicle/service metrics and assertion evidence in primary GUI | PASSED by reinspection | Energy requested/delivered/unmet/pending shown; assertion metadata flattened with actual verdict and paired means; counterexamples expandable with case/time/threshold and raw details. |
| Primary GUI comparison, cancellation/resume and YAML IO | PASSED with limit | Parent exercised actual YAML import, immutable save/run, cancel/resume and incompatible comparison. Export button clicked, but downloaded contents were not verified. |
| Real Codex CLI tool calling | PASSED | `codex_chat.json`: four real MCP calls; validated/saved/started returned run IDs. |
| Workers survive Codex CLI exit | PASSED | Same evidence reports two completed cases after CLI exit; loopback broker owned by long-lived app process. |
| Chat failure recovery | PASSED by reinspection | POST/poll recovery plus busy guard prevents Enter resubmission while a turn is active. |
| Latest full repository checks and browser acceptance | PASSED on combined evidence | Current hashes match 42-test Python/API/MCP freeze. Parent browser workflow evidence and independent API result agreement are attributed separately in react_browser.json. |

## Correction loops and acceptance

Reported source blockers are closed: static/dynamic map metadata, separate transformer histories, nested assertion verdict/counterexamples, chat busy/error handling, map unknown state, chart gaps, scope label, conditional stop guidance, notebook execution, YAML IO and lifecycle controls. The full vehicle-state table now exposes charging, waiting, completed, connected and cumulative departure shortfall with its timing convention.

Parent browser checks exercised real OSM/car popups and counts, HH:MM/day axes, invalid JSON, seasonal presets and growth preview, actual winter YAML file import, save/run, a deliberate 1% loading stop with warning and counterexample, incompatible comparison, live Codex MCP chat, cancellation and resumed completion. Independent API observations agreed with the selected displayed counts and stop evidence.

The final browser found a heatmap transition defect caused by repeated React keys on a single-interval result. The key now uses position. Parent rechecked the final BU0-sOQ8 build through CUA DOM and screenshot: switching from the one-interval stop to the full trajectory produces one five-label row (00:00, 08:15, 16:30, D2 00:30, D2 08:45), without accumulated duplicate labels. Updated fingerprints and the attributed regression are recorded in react_browser.json.

**MVP accepted on combined evidence.** This is not a claim that a second agent independently operated the browser: its browser attempts were unavailable. Fresh plugin manifest/stdio execution was tested, but pickup in a brand-new Codex desktop conversation was not. Downloaded YAML export contents were not independently verified. These limits remain explicit and do not turn source inspection into exercised evidence.

## Non-blocking model limitations

The reduced feeder approximation does not preserve every detailed-grid voltage or shared feeder interaction. The selected comparison is evidence of this discrepancy, not calibration. Public hubs and charging behavior are assumptions. Results test hypotheses within that model and do not establish operational hosting capacity. The larger network remains optional and does not run implicitly.

## Final evidence audit

The final 42-test engine fingerprint and app source hashes in `testing.json/final_python_app_freeze` were independently compared with the current files and match. Actual stdio lifecycle evidence includes discovery, invalid input, save, run, cancellation, server restart, resume, results, revision and comparison. Notebook execution and real Codex CLI worker survival have separate evidence.

Primary browser coverage is now recorded with provenance in `react_browser.json`. Exact vehicle-state counts and the stale 28-test documentation were corrected; the guide now references the final 42 tests and distinguishes React clocks from legacy diagnostic elapsed-hour axes.

## Closure rule

The correction loops are closed for this MVP. Future changes require checks appropriate to the affected behavior. Preserve the distinction between independent backend testing, parent-operated browser evidence and unverified export/plugin-client details; do not describe this synthetic model as utility validated.
