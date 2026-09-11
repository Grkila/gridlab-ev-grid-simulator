# Desktop experiment workflow

The primary navigation contains Experiments, Results, and Network. Research tools expands to Strategies, Benchmarks, and Train a controller; Overview remains available as a secondary link.

Experiment setup has four stages: Scenario, Vehicles, Strategies, and Review. Stage buttons allow direct movement without clearing edits. Custom calibration, capacity overrides, randomized demand, vehicle placement, and solver settings are expandable. Review summarizes the configured experiment and provides the full definition for inspection.

Save only stores an immutable experiment. Save & run stores the same immutable definition, then starts a run using the returned experiment ID and opens Results. If starting fails, the saved experiment remains in Saved experiments and its Run button can retry. Neither action changes the simulation contract or acceptance criteria.

Compare runs is beside the run selector. Opening it exposes the existing 2–8 run selection, selection count, comparison action, and evidence compatibility explanations above individual results.

Pages and the selected run use query parameters, for example `?view=results&run=run-example`. Navigation uses links with normal new-tab behavior. Browser Back, Forward, and reload restore the selected page and run; stale result requests are ignored after changing runs. Unsaved experiment drafts remain in memory while navigating inside the app and are not saved by a URL.

## Verification — 2026-09-11

- `npm --prefix web run build`: passed.
- `.venv/Scripts/python.exe -m unittest discover -s tests -v`: 253 tests passed in 147.403 seconds; log at `artifacts/playground/gui-streamline-tests.log`.
- `node scripts/verify_streamlined_gui.cjs` with Playwright in `NODE_PATH`: passed production-build browser checks for navigation, stage inputs, save/start request ordering, save-only behavior, failed-start recovery, Back/reload restoration, comparison, and invalid JSON. API boundaries are mocked; no real simulation is started by this verifier.
- Read-only desktop inspection of the running app on port 8534: saved experiment catalog and new setup rendered without browser errors. That runtime had no experiment runs, so run history and comparison interactions were verified by the isolated browser fixture. Screenshot: `artifacts/playground/evidence/streamlined-live-desktop.png`.

The build retains a large JavaScript chunk warning. Responsive styling was checked during implementation; desktop is the requested focus.
