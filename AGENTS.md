# Agent instructions

This file governs the whole repository. A more specific `AGENTS.md` adds rules for its subtree.

## Required reading order

Before editing, read:

1. `README.md`
2. `.agents/PROJECT_MEMORY.md`
3. `.agents/DECISIONS.md`
4. `docs/architecture.md`
5. The nearest folder-specific `AGENTS.md`

Do not claim durable chat memory. Repository files are the project memory. Follow `.agents/README.md` when recording new facts.

## Invariants

- The Novi Sad outputs must describe one shared topology across the network, map, manifests, and validation report.
- The model is a synthetic planning proxy, never an as-built EDS model.
- Keep paths independent of the current working directory; use `mvgrid.paths`.
- Keep source in `src/`, launchers in `scripts/`, configurations in `configs/`, reference data in `data/`, and generated deliverables in `artifacts/`.
- Never commit virtual environments, caches, logs, secrets, or pickle files.
- Do not hand-edit generated data or claim calibration as independent validation.
- Preserve upstream attribution and OSM/ODbL attribution.

## Completion gate

Run `python -m unittest discover -s tests -v`, run the appropriate workflow, inspect `git status`, and update durable documentation when behavior or verified baselines change. Do not push a failing or partially generated reference set.
