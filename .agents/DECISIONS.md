# Architecture decisions

## 2026-09-10: Package and folder boundaries

Source code uses a `src/mvgrid` package. The original GUI workflow is isolated under `legacy`; Novi Sad code is under `novi_sad`. All repository paths are defined in `mvgrid.paths`, so commands work outside the repository directory.

## 2026-09-10: Reference artifact exception

One challenge reference set remains versioned under `artifacts/novi_sad/reference/`, including the large pandapower JSON and HTML map. This favors an inspectable handoff over repository size. Future large snapshots should use a GitHub Release rather than normal Git history.

## 2026-09-10: Cache and reproducibility boundary

Python pickle and live OSM caches remain ignored under `data/cache/`. A manifest with hashes and dependency versions provides traceability. This is not described as clean-clone reproducibility.
