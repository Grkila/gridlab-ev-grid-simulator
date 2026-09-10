# Artifacts

`novi_sad/reference/` contains the single challenge handoff set:

- `models/`: pandapower JSON, compact results, and model manifest.
- `maps/`: interactive HTML map of the same topology.
- `reports/`: machine-readable and human-readable validation reports.
- `reference_manifest.json`: LF-normalized SHA-256 and size inventory binding the complete reference set across operating systems.

These large files remain in normal Git as a documented challenge exception. Do not add timestamped or alternate snapshots here; publish future large bundles as release assets with checksums.
