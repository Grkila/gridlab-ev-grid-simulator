# District capacity implementation review

Status: ACCEPTED for the authorized estimated-district-capacity MVP.
Date: 2026-09-10.

## Scope and verdict

The implementation follows the agreed simplification: the existing small pandapower topology, estimated district kW budgets independent of experiment demand, low/central/high sensitivity, provenance-bearing per-district central overrides, district vehicle placement, and separate upstream electrical checks. No MV/LV assets were added and NS1, NS6 and FUT remain excluded.

A district capacity exceedance is a planning constraint event, not a prediction of transformer damage or protection operation. The default central budget is delivery-station MVA multiplied by 1,000, assumed power factor 0.97, and planning factor 0.8. Sensitivity factors 0.8/1/1.2 apply to both default central estimates and explicit central overrides. These are engineering assumptions, not verified utility limits.

No remaining must-fix issue was identified against this scope.

## Verified behavior

- Every retained delivery district receives a positive estimated capacity with provenance and resolved sensitivity factor.
- Capacity resolution has no demand input. Seasonal demand, growth, composition and fleet changes do not resize capacities.
- All assigned blocks and public hubs share one district budget. Unmanaged charging can exceed it; capacity-aware charging budgets shared headroom.
- Events record district, demand, capacity and affected blocks. Default stopping preserves the first violating interval and incomplete evidence.
- District metrics and assertions remain distinct from pandapower line, voltage and transformer violations.
- Resolved capacities are frozen in run manifests. Changed capacity assumptions prevent a pure controller paired comparison.
- Guided district allocation supports zero shares and concentration in one district. Clearing a capacity override restores the default.
- The GUI displays estimated capacity, demand, utilization, headroom, provenance and vehicle counts. Historical runs without capacity evidence display unavailable values.
- MCP schema, exported schema, example definitions, workflow skill and documentation agree. The notebook consumes the live contract.

## Final evidence

Primary record: `artifacts/playground/evidence/district-capacity.json`.

- All 52 tests passed in 73.318 seconds. Actual stdio MCP lifecycle and district-specific counterexample, placement and comparison checks passed.
- The reviewer independently compared the recorded engine fingerprint and final frontend hashes with current files: both match.
- The final frontend files are `index-Dlk5z3gM.js` and `index-8p8b4As6.css`. These supersede earlier reviewed builds.
- Parent-operated browser testing used 100 percent NS5 placement and a 1,000 kW central override under the low scenario, resolving to 800 kW. All 100 generated sessions belonged to NS5.
- At 19:30, saved NS5 counts were 39 connected, 31 charging, zero waiting, eight completed and two cumulative departure shortfalls. Demand was 520.6548491601031 kW and headroom 279.34515083989686 kW against 800 kW capacity, agreeing with the reported GUI.
- A separate stopped run recorded a district-only exceedance at its first interval: approximately 236.45 kW against 0.8 kW. The warning identified estimated capacity, the result remained incomplete, and upstream equipment was not falsely marked as violating.
- Final viewport regression passed after `.panel { min-width: 0 }` allowed the wide table to scroll inside its panel. The parent observed a 1,022-pixel viewport and document width, panel right edges at 990 pixels, and visible district selector and clock axes.
- Six repository rechecks and the legacy diagnostic AppTest passed after final integration. Notebook cells executed top-to-bottom with a text display adapter and Agg backend; this is not a Jupyter-kernel execution claim.

## Review provenance

This monitor inspected evolving source, sent corrections before completion, executed direct simulator probes and focused tests, checked schema equality, and compared evidence fingerprints. Browser interactions and screenshots are attributed to the parent agent and were not independently repeated by this monitor. The reviewer previously implemented the network reduction; this review does not certify that synthetic topology as an independently verified utility model.

## Correction history, 2026-09-10

All items below are closed:

1. Corrected override wording to say the override replaces the central estimate and still receives the sensitivity factor.
2. Corrected clearing an override and zero-share editing to remove the corresponding keys rather than create invalid configuration.
3. Added capacity configuration to comparison compatibility and retained historical-result behavior.
4. Confirmed distinct district stop evidence and shared controller headroom without suppressing upstream checks.
5. Corrected a review-document encoding error; this final record is explicitly UTF-8 with ASCII punctuation.
6. Corrected wide-panel overflow and rechecked the final production viewport and asset hashes.

Software acceptance establishes the implemented workflow and declared model behavior. It does not establish real district operating capacities or physical failure limits.
