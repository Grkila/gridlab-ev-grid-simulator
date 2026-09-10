# Project memory

Last verified: 2026-09-10

## Purpose

The Schneider challenge fork adapts the upstream OSM MV-grid generator into one unified Novi Sad planning workflow. The legacy GUI remains available under `src/mvgrid/legacy/`.

## Verified reference baseline

- Status: `INTERNAL_CONSISTENCY_PASS`
- 2,648 loads; 21,783 buses; 21,759 lines; 15 transformers; 9 external grids
- Nine radial source islands using NS1, NS2, NS4, NS5, NS6, NS7, NS9, RIM, and FUT
- Base load 214.854 MW; minimum voltage 0.956792 pu
- Maximum line loading 72.2904%; maximum transformer loading 88.3325%
- Evidence: `artifacts/novi_sad/reference/reports/novi_sad_validation_report.json`

## Durable caveats

- The demand points, feeder routes, several station coordinates, associations, and equipment parameters are inferred.
- The annual energy is a calibration input and the peak is derived with a 1.64 peak-to-mean ratio.
- `data/cache/data.pkl` is ignored. Its SHA-256 is recorded in the input manifest, so the reference set is traceable but a clean clone is not bit-for-bit reproducible.
- Large reference artifacts are kept in Git for the challenge handoff. Regeneration will create large diffs; do not add additional snapshots.
