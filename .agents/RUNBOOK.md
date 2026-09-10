# Runbook

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
