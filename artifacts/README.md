# Artifacts

`handoff/screenshots/` contains the English application and presentation captures.
See [screenshot coverage](../docs/SCREENSHOTS.md) and [Windows verification](../docs/handoff-verification.md).

`playground/` retains published evidence and local runtime catalogs.
Git ignores saved experiments, runs, archived catalogs, training output, and chat storage.
Removing their Git tracking preserves the current local copies.
`challenge-study-v2/` retains the frozen published study, including its evidence.

`novi_sad/reference/` contains the single challenge handoff set:

- `models/`: pandapower JSON, compact results, and model manifest.
- `maps/`: interactive HTML map of the same topology.
- `reports/`: machine-readable and human-readable validation reports.
- `reference_manifest.json`: LF-normalized SHA-256 and size inventory binding the complete reference set across operating systems.

These large files remain in normal Git as a documented challenge exception. Do not add timestamped or alternate snapshots here; publish future large bundles as release assets with checksums.
