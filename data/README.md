# Data layout

- `novi_sad/reference/inputs/`: small versioned OSM-derived input extracts.
- `novi_sad/reference/generated/`: deterministic intermediate tables, routes, and manifests for the single committed reference model.
- `cache/`: ignored local stage state and download caches, including `data.pkl`.

Do not load a pickle supplied by an untrusted party. See `docs/data-sources-and-licenses.md` and `docs/reproducibility.md` before publishing or replacing data.

`novi_sad_boundary_raw.json` preserves the raw boundary response used to inspect and document the Novi Sad study-area selection. The current pipeline reads the processed polygon from the trusted stage cache, so this file is provenance evidence rather than a runtime input.
