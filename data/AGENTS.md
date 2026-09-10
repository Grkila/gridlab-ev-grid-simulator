# Data rules

- `reference/inputs` contains versioned source snapshots; treat them as immutable and document provenance.
- `reference/generated` contains deterministic intermediates for the single reference model; regenerate them through the pipeline, never by hand.
- `cache/` is ignored runtime state. Never commit pickle files or downloaded caches.
- External data is not relicensed by the repository MIT license. Preserve source attribution and terms.
