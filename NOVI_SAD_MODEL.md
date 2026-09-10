# Novi Sad 20-kV demonstrator

Run the complete non-GUI workflow on Windows:

```powershell
.\.venv\Scripts\python.exe run_novi_sad.py
```

The generated `ppnet_novi_sad.json` is a reproducible OSM-based **central/northern Novi Sad 20-kV demonstrator**, not a feeder-level digital twin. OSM lacks complete transformer inventory, ratings, SCADA and load time series. The run therefore uses three confirmed 110/20-kV sources: Novi Sad 7 (OSM way 220232167), Novi Sad 5 (365786756), and Rimski Sancevi (365927134). Each has one 63-MVA aggregate 110/20-kV transformer modelled; it does not model two 63-MVA units.

The load model is spatially allocated from OSM land use, then calibrated to 104.1 MW aggregate peak: three 63-MVA sources at a 55% planning load. Each inferred corridor represents three parallel 150-mm² 20-kV cables, rather than one cable; this is necessary to reflect a multi-circuit urban feeder system and is consistent with the reported multiple NS5–NS7 interties. This is an intentionally bounded proxy, not the complete city demand. The literature case study reports 433-MW city peak across 15 110/x-kV sources, 2,308 GWh/year and an approximately 1.64 peak-to-mean ratio. The supplied 2025 planning graphic is retained as a separate system-level reference (598 MW at 10 kV, 299 MW at 20 kV, 120 MW at 0.4 kV; 1,178 MW installed), rather than incorrectly assigning all of it to this three-source model.

Sources: [Novi Sad grid case study](https://link.springer.com/article/10.1007/s00202-021-01271-z), [Novi Sad 7 OSM feature](https://www.openstreetmap.org/way/220232167), [Novi Sad 5 OSM feature](https://www.openstreetmap.org/way/365786756), and [official Rimski Sancevi commissioning notice](https://novisad.rs/lat/pustena-u-pogon-nova-trafostanica-11020kv-rimski-sancevi).

## City-scale inferred overlay

The interactive map is a larger planning overlay and must not be confused with
the 42-bus pandapower demonstrator above. Generate it with:

```powershell
.\.venv\Scripts\python.exe generate_synthetic_transformers.py
.\.venv\Scripts\python.exe generate_inferred_feeders.py
.\.venv\Scripts\python.exe generate_novi_sad_map.py
```

The overlay seeds the nine primary stations listed by EDS for the Novi Sad
branch: Novi Sad 1, 2, 4, 5, 6, 7 and 9, Rimski Sancevi, and Futog. Seven have a
direct 110/20-kV function. Novi Sad 2 and Novi Sad 4 remain explicitly on a
legacy 110/35-kV path to the Liman, Centar, Podbara, Sever, Industrijska and
Telep 35/10-kV stations. Equipment ratings, 2024 Pmax and reported utilization
come from the official EDS 2025-2034 development plan (base year 2024).
The documented upstream associations NS2-Centar and NS4-Liman are fixed in the
overlay; the other four legacy upstream assignments and every drawn street
corridor are explicitly labelled as inferred.

Only Novi Sad 5, Novi Sad 7 and Rimski Sancevi have name-confirmed coordinates
in OSM. Every other station-to-OSM-feature association is marked as inferred.
The 2,648 synthetic service points retain the supplied total of 1,147,635
MWh/year and 214.854 MW calibrated peak. Feeder geometry is a capacity-balanced
shortest-path forest on road-like OSM edges; ferries, steps, paths, footways,
cycleways and pedestrian-only edges are excluded. Every source-specific feeder
graph is radial and every source allocation stays below 95% of the corresponding
direct 20-kV nameplate. These paths are hypotheses for scenario testing, not
utility records or surveyed cable routes.

The present synthetic demand footprint is the Novi Sad urban study polygon used
by the repository, not the full administrative territory of Grad Novi Sad. Futog
and other primary seeds outside that polygon are retained and connected with
dotted, explicitly inferred catchment connectors. Expanding demand to every
outlying settlement requires a larger OSM/building extraction and a separate
consumption-allocation assumption; this overlay does not silently invent it.

Official source: [EDS Plan razvoja distributivnog sistema 2025-2034](https://elektrodistribucija.rs/regulativa/propisi/dokumenta/Plan_razvoja_2025_2034.pdf), especially the Novi Sad base-year tables on PDF pages 162 and 164.
