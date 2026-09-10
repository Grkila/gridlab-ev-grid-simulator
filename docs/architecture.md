# Architecture

The repository has two workflows inside one Python package.

`mvgrid.legacy` contains the original staged OSM reconstruction and GUI. `mvgrid.novi_sad` consumes the stage cache and deterministically creates synthetic demand points, a capacity-balanced inferred feeder forest, one pandapower model, a map, and validation reports.

```text
configs + local OSM snapshot
            |
            v
  legacy stages (0-3)
            |
            v
 synthetic transformers -> inferred feeders -> pandapower model
                                      |                |
                                      v                v
                                     map          validation
```

`mvgrid.paths` owns all repository paths. Source modules must not depend on the caller's working directory. Checkout launchers add `src` to `sys.path`; editable installation exposes equivalent console commands.

Versioned reference intermediates live in `data/novi_sad/reference/generated`. User-facing outputs live in `artifacts/novi_sad/reference`. Runtime pickle and HTTP caches live in ignored `data/cache`.
