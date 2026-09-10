# Runbook

## Loss-aware and voltage-regulated tests

The active updated preview is `http://127.0.0.1:8533`. Rebuild with `npm --prefix web run build` and use a fresh backend after source changes. New presets reconcile loss-inclusive input; `load` retains an explicit legacy delivered-load interpretation. The GUI offers **Voltage-regulated grid** (1.04 pu source voltage and daily-energy-preserving 220 MW baseline peak shifting) or original operating assumptions.

Run `python scripts/create_loss_test_experiments.py` to validate/save the five regulated experiments through fresh MCP. Run `python scripts/run_loss_capacity_study.py --mode regulated --reference 500 --max-fleet 5000` for the current ten-test comparison; it holds a fresh MCP connection and records IDs/results under `artifacts/playground/regulated-capacity-study`. `--job <id>` reads an existing job instead of starting another. Do not duplicate a live worker.

`scripts/diagnose_baseline.py`, `scripts/test_baseline_interventions.py` and `scripts/test_winter_voltage.py` are explicit model/operating-assumption diagnostics. Original pre-correction evidence is under `artifacts/playground/baseline-diagnosis`; do not overwrite it to claim the original network was already corrected. Retired experiment catalogs are outside runtime under `artifacts/playground/retired-before-loss-correction-20260910`.

From a checkout with the environment activated:

```powershell
python -m unittest discover -s tests -v
python scripts/run_novi_sad.py
python scripts/run_novi_sad.py --skip-map --skip-validation
python scripts/run_legacy_gui.py
```

To verify working-directory independence, run the absolute path to `scripts/run_novi_sad.py` while located outside the repository. Use `--refresh-osm` only when intentionally accepting live OSM changes.

Before a release or push, confirm the validation status is `INTERNAL_CONSISTENCY_PASS`, inspect large-file changes, scan for secrets and caches, and ensure `git status` contains only intentional files.

For the React playground, rebuild with `npm --prefix web run build` and restart `python scripts/run_playground_app.py` after changing backend code or network inputs. The updated server keys its map cache on the generated network file revision; Refresh picks up a rebuilt topology. Older server processes require restart. Before restarting, check that no simulation is running. Reload the browser afterward and verify Network shows three excluded sources and 100% retained demand for the current whole-city model. This resolved stale six-source map data during GUI testing on 2026-09-10.
# RL verification

Run `.venv/Scripts/python.exe scripts/verify_playground_rl.py` for bounded real AC
training and held-out comparisons in the normal runtime store. It creates a fresh
four-episode demonstration model and saves measured evidence; it does not prove
policy quality. For configuration and artifact semantics see `docs/models/ev-rl.md`.

## Standard benchmark

Build the frontend, then start a fresh playground server. Open Benchmarks, freeze a suite, select registered strategies and run. Reuse the suite for revised or new algorithms; raise the search ceiling in a new suite when the old ceiling passes. A small ceiling is workflow verification only. Run `python scripts/verify_benchmark.py --url http://127.0.0.1:8532` for the bounded real 30-cell workflow, `python scripts/verify_benchmark_mcp.py` for fresh MCP discovery, and `node scripts/verify_benchmark_gui.cjs` with Playwright available in NODE_PATH for browser acceptance. The GUI verifier defaults to port 8532; override EV_GUI_URL as needed. See `docs/benchmark.md`.
