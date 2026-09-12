# Screenshot coverage

The current README uses actual Windows Chromium captures at 1440 by 960 pixels.
Focused panel images show individual charts without a full-page sidebar.
The capture checks wait for saved evidence and loaded map tiles.

The [asset notes](../artifacts/handoff/showcase/README.md) identify source records and distinguish real, interrupted, and illustrative evidence.
Runtime JSON stays local. The banner is generated concept artwork.

## Application feature coverage

| Feature or state | Instructions | Image |
| --- | --- | --- |
| overview | [Procedure](USER_GUIDE.md#navigation) | [overview.png](../artifacts/handoff/showcase/overview.png) |
| experiment scenario | [Procedure](USER_GUIDE.md#experiments) | [experiment-scenario.png](../artifacts/handoff/showcase/experiment-scenario.png) |
| demand assumptions | [Procedure](USER_GUIDE.md#experiments) | [demand-assumptions.png](../artifacts/handoff/showcase/demand-assumptions.png) |
| capacity assumptions | [Procedure](USER_GUIDE.md#experiments) | [capacity-assumptions.png](../artifacts/handoff/showcase/capacity-assumptions.png) |
| charging profile | [Procedure](USER_GUIDE.md#experiments) | [charging-profile.png](../artifacts/handoff/showcase/charging-profile.png) |
| optimization settings | [Procedure](USER_GUIDE.md#experiments) | [optimization-settings.png](../artifacts/handoff/showcase/optimization-settings.png) |
| experiment review | [Procedure](USER_GUIDE.md#experiments) | [experiment-review.png](../artifacts/handoff/showcase/experiment-review.png) |
| experiment json | [Procedure](USER_GUIDE.md#experiments) | [experiment-json.png](../artifacts/handoff/showcase/experiment-json.png) |
| demand dashboard | [Procedure](USER_GUIDE.md#results) | [demand-dashboard.png](../artifacts/handoff/showcase/demand-dashboard.png) |
| exact demand | [Procedure](USER_GUIDE.md#results) | [exact-demand.png](../artifacts/handoff/showcase/exact-demand.png) |
| cars at 09 | [Procedure](USER_GUIDE.md#results) | [cars-at-09.png](../artifacts/handoff/showcase/cars-at-09.png) |
| cars at 13 | [Procedure](USER_GUIDE.md#results) | [cars-at-13.png](../artifacts/handoff/showcase/cars-at-13.png) |
| cars at 19 | [Procedure](USER_GUIDE.md#results) | [cars-at-19.png](../artifacts/handoff/showcase/cars-at-19.png) |
| cars at 22 | [Procedure](USER_GUIDE.md#results) | [cars-at-22.png](../artifacts/handoff/showcase/cars-at-22.png) |
| car count popup | [Procedure](USER_GUIDE.md#results) | [car-count-popup.png](../artifacts/handoff/showcase/car-count-popup.png) |
| loading heatmap | [Procedure](USER_GUIDE.md#results) | [loading-heatmap.png](../artifacts/handoff/showcase/loading-heatmap.png) |
| district headroom | [Procedure](USER_GUIDE.md#results) | [district-headroom.png](../artifacts/handoff/showcase/district-headroom.png) |
| capacity dashboard | [Procedure](USER_GUIDE.md#results) | [capacity-dashboard.png](../artifacts/handoff/showcase/capacity-dashboard.png) |
| network loaded | [Procedure](USER_GUIDE.md#network) | [network-loaded.png](../artifacts/handoff/showcase/network-loaded.png) |
| algorithm library | [Procedure](USER_GUIDE.md#strategies) | [algorithm-library.png](../artifacts/handoff/showcase/algorithm-library.png) |
| algorithm assumptions | [Procedure](USER_GUIDE.md#strategies) | [algorithm-assumptions.png](../artifacts/handoff/showcase/algorithm-assumptions.png) |
| codex propose | [Procedure](USER_GUIDE.md#strategies) | [codex-propose.png](../artifacts/handoff/showcase/codex-propose.png) |
| codex specify | [Procedure](USER_GUIDE.md#strategies) | [codex-specify.png](../artifacts/handoff/showcase/codex-specify.png) |
| codex build | [Procedure](USER_GUIDE.md#strategies) | [codex-build.png](../artifacts/handoff/showcase/codex-build.png) |
| codex compare | [Procedure](USER_GUIDE.md#strategies) | [codex-compare.png](../artifacts/handoff/showcase/codex-compare.png) |
| codex challenge | [Procedure](USER_GUIDE.md#strategies) | [codex-challenge.png](../artifacts/handoff/showcase/codex-challenge.png) |
| codex revise | [Procedure](USER_GUIDE.md#strategies) | [codex-revise.png](../artifacts/handoff/showcase/codex-revise.png) |
| codex handoff | [Procedure](USER_GUIDE.md#strategies) | [codex-handoff.png](../artifacts/handoff/showcase/codex-handoff.png) |
| benchmark setup | [Procedure](USER_GUIDE.md#benchmarks) | [benchmark-setup.png](../artifacts/handoff/showcase/benchmark-setup.png) |
| benchmark rationale | [Procedure](USER_GUIDE.md#benchmarks) | [benchmark-rationale.png](../artifacts/handoff/showcase/benchmark-rationale.png) |
| benchmark dashboard | [Procedure](USER_GUIDE.md#benchmarks) | [benchmark-dashboard.png](../artifacts/handoff/showcase/benchmark-dashboard.png) |
| benchmark matrix | [Procedure](USER_GUIDE.md#benchmarks) | [benchmark-matrix.png](../artifacts/handoff/showcase/benchmark-matrix.png) |
| benchmark capacity chart | [Procedure](USER_GUIDE.md#benchmarks) | [benchmark-capacity-chart.png](../artifacts/handoff/showcase/benchmark-capacity-chart.png) |
| benchmark trial evidence | [Procedure](USER_GUIDE.md#benchmarks) | [benchmark-trial-evidence.png](../artifacts/handoff/showcase/benchmark-trial-evidence.png) |
| ppo demo | [Procedure](USER_GUIDE.md#training) | [ppo-demo.png](../artifacts/handoff/showcase/ppo-demo.png) |
| ppo demo learning | [Procedure](USER_GUIDE.md#training) | [ppo-demo-learning.png](../artifacts/handoff/showcase/ppo-demo-learning.png) |
| ppo interrupted | [Procedure](USER_GUIDE.md#training) | [ppo-interrupted.png](../artifacts/handoff/showcase/ppo-interrupted.png) |
| binary training settings | [Procedure](USER_GUIDE.md#training) | [binary-training-settings.png](../artifacts/handoff/showcase/binary-training-settings.png) |
| binary interrupted | [Procedure](USER_GUIDE.md#training) | [binary-interrupted.png](../artifacts/handoff/showcase/binary-interrupted.png) |
| rl reward | [Procedure](USER_GUIDE.md#results) | [rl-reward.png](../artifacts/handoff/showcase/rl-reward.png) |
| per car demand | [Procedure](USER_GUIDE.md#results) | [per-car-demand.png](../artifacts/handoff/showcase/per-car-demand.png) |
| charger timeline | [Procedure](USER_GUIDE.md#results) | [charger-timeline.png](../artifacts/handoff/showcase/charger-timeline.png) |

## Inspection and supplemental states

All current viewport images keep the sidebar at the full viewport height.
Map captures include loaded street tiles and visible OSM attribution.
The benchmark dashboard intentionally shows a failed historical job with retained rows.
The binary training and PPO campaign images retain their interrupted and budget-limited status.
The PPO demo identifies its synthetic data on screen.

Earlier empty, error, comparison, and advanced-form captures remain in the [supplemental inventory](SCREENSHOTS-ARCHIVE.md).
Those earlier full-page images are not the current README showcase.

Generate inspection sheets with `scripts/review_readme_images.py`.

- [Inspection sheet 01](../artifacts/handoff/showcase/contact-01.png)
- [Inspection sheet 02](../artifacts/handoff/showcase/contact-02.png)
- [Inspection sheet 03](../artifacts/handoff/showcase/contact-03.png)
- [Inspection sheet 04](../artifacts/handoff/showcase/contact-04.png)
- [Inspection sheet 05](../artifacts/handoff/showcase/contact-05.png)
- [Inspection sheet 06](../artifacts/handoff/showcase/contact-06.png)
- [Inspection sheet 07](../artifacts/handoff/showcase/contact-07.png)
- [Inspection sheet 08](../artifacts/handoff/showcase/contact-08.png)
- [Inspection sheet 09](../artifacts/handoff/showcase/contact-09.png)
- [Inspection sheet 10](../artifacts/handoff/showcase/contact-10.png)
- [Inspection sheet 11](../artifacts/handoff/showcase/contact-11.png)
