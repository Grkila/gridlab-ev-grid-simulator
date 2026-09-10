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
