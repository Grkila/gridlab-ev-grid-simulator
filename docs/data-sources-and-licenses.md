# Data sources and licenses

## OpenStreetMap

Study boundaries, land-use features, street geometry, and mapped electrical features are derived from [OpenStreetMap](https://www.openstreetmap.org/copyright). Credit: © OpenStreetMap contributors. OSM data is available under the [Open Data Commons Open Database License](https://opendatacommons.org/licenses/odbl/1-0/). Produced works and extracted databases may carry obligations beyond the repository's MIT code license.

The committed JSON and GeoJSON snapshots preserve only data needed for the reference challenge model. The local cache hash and configuration identity are recorded in `data/novi_sad/reference/generated/novi_sad_input_manifest.json`. The legacy cache did not retain authoritative per-query acquisition timestamps, and the manifest labels that gap explicitly.

## Elektrodistribucija Srbije planning data

Station ratings, reported peak values, and planning totals were transcribed from the [EDS distribution-system development plan 2025–2034](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf). Consult the publisher for authoritative terms and current values. The repository does not relicense that source material.

## Code and third-party software

Repository code is MIT-licensed as stated in `LICENSE`. Dependencies keep their own licenses. External data does not become MIT-licensed merely because it is stored beside the code.
