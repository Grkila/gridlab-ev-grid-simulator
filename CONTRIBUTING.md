# Contributing

Use Python 3.10 or 3.11 and install `requirements.txt` plus the editable package. Keep changes focused, preserve upstream attribution, and do not commit runtime caches or additional large generated snapshots.

Before opening a change:

1. Read `AGENTS.md` and the nearest folder instructions.
2. Run `python -m unittest discover -s tests -v`.
3. Run the affected workflow offline against the known snapshot.
4. If the reference model changes, regenerate every related intermediate, model, map, manifest, and report together.
5. Explain whether changed metrics are intentional and update `.agents/PROJECT_MEMORY.md` only after verification.

Live OSM refreshes are inherently time-dependent. Keep those changes separate from code refactors so reviewers can distinguish data drift from behavior changes.
