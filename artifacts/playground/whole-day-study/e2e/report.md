# MVP frontend/backend verification

The tested MVP workflows pass against a real local backend. The browser test recorded 84 check entries (including polling) and 242 successful API responses across 23 distinct method/path pairs. No browser exception or failed API response occurred in the normal browser workflow.

Final verification: all 286 repository tests passed in 152.6 seconds. The production TypeScript/Vite build, 303 slider-transition checks and separate browser error-recovery checks also passed.

| Area | What was verified |
| --- | --- |
| Experiments | Validate, save, start the real worker, poll, reload persisted results |
| Whole-day simulation | 12 cars, 132 intervals, 168 battery kWh delivered, zero unmet energy |
| Results | Rename, delete, undo deletion, compare saved runs |
| Benchmark setup | Read cancelled evidence correctly; freeze a small home-only suite without executing it |
| Strategies | Read the library, save a proposal through HTTP, read the saved record |
| Pages | Overview, Network, Results, Experiments, Strategies, Benchmarks, Training and presentation load |
| Percentages | Linked sliders stay at 100%, including keyboard and 0/100% edges; desktop and mobile layouts checked |
| Errors | Invalid definitions, unknown records, invalid commands, wrong runtime root and malformed requests rejected |
| Optional workers | Chat and training lifecycle HTTP contracts tested with worker services stubbed |
| Live application | Ten live catalog/read endpoints, local geography JSON and presentation iframe acknowledgements pass; slide navigation issues no POSTs |

Review found and fixed a profile propagation bug in the optional campaign factory: it now regenerates the selected whole-day profile and includes that generator in its source fingerprint. Independent tests cover whole-day, home-only and historical profiles.

This is functional MVP verification, not load testing or proof of every concurrency race. External Codex authentication and live training were not exercised. The full benchmark was cancelled at the user's request after 42/70 rows; no capacity ranking is claimed from those partial results.

Evidence: `results.json`, `live-readonly.json`, `desktop.png`, `mobile.png`, the parent `final-unittest.log`, and the independent parent `review.md`. Repeat with `scripts/run_api_e2e.py`, `scripts/verify_live_readonly.cjs`, `scripts/verify_charging_profiles_gui.cjs` and `python -m unittest discover -s tests -v`.
