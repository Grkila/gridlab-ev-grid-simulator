# Methodology

The upstream workflow queries OpenStreetMap for the study polygon, land use, streets, and known electrical features. The Novi Sad adaptation then creates 2,648 seeded synthetic service points, calibrates their annual energy to 1,147,635 MWh, and derives a 214.854 MW coincident peak using a 1.64 peak-to-mean assumption.

Service points are snapped to the road graph and allocated to delivery roots subject to planning capacities. Shared shortest-path street edges form a radial feeder forest. The electrical model represents nine primary sources; NS2 and NS4 supply inferred 35/10 kV legacy paths while the other stations deliver directly at 20 kV.

The model uses generic planning cable and transformer parameters where authoritative asset data is unavailable. Validation checks internal topology, traceability, connectivity, geodata, power-flow convergence, voltage, loading, and losses. Matching the annual-energy input is calibration—not independent validation.

Detailed station assumptions and acceptance limits are in [`models/novi-sad.md`](models/novi-sad.md).
