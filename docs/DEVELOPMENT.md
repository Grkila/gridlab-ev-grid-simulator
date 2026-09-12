# Local development on Windows

Run [Windows setup](../README.md#start-on-windows) before using these commands.
The standard setup includes both RL backends. This repository has no CI/CD workflow.

## Build and test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix web run build
```

Run these commands from the repository root. The application start scripts also support other working directories.
Use `npm.cmd` to avoid PowerShell restrictions on the npm script wrapper.

## Browser verification

Install the browser used by Playwright:

```powershell
node .\web\node_modules\playwright\cli.js install chromium
```

Start the app in another terminal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -NoBrowser
```

Check the presentation and its street geometry:

```powershell
node .\scripts\verify_presentation.cjs
node .\scripts\verify_presentation_roads.cjs
```

Run the isolated application workflow:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_api_e2e.py
```

The verifier creates a small local experiment and benchmark suite. It does not require saved study runs.
It tests real HTTP operations, experiment execution, run management, comparisons, and browser controls.
Its runtime directories remain ignored. Test data is not scientific capacity evidence.

Check Windows launch failures and bounded training with:

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_windows_launch.py
.\.venv\Scripts\python.exe .\scripts\verify_handoff_training.py
```

## Screenshots

```powershell
node .\scripts\capture_documentation.cjs http://127.0.0.1:8517
.\.venv\Scripts\python.exe .\scripts\make_documentation_contact_sheets.py
```

The capture script navigates the actual application and blocks API writes.
Use meaningful local results to populate result views. It never starts runs or sends chat messages.
It also updates the presentation's application captures, so rebuild the frontend after capture.
Inspect all images before publishing documentation.

For empty-state captures, start a separate server with an isolated catalog:

```powershell
$env:EV_PLAYGROUND_HOME = Join-Path (Get-Location) 'artifacts\handoff\runtime-empty'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -NoBrowser -Port 8518
```

Use a new terminal for this command. Keep the populated server on port 8517.
Run `node scripts/capture_documentation_states.cjs` from a third terminal.
This capture checks completed responses before saving comparison images. It does not start experiments or send chat messages.

## README showcase captures

The current README uses `scripts/capture_readme_showcase.cjs`.
It captures a 1440 by 960 Windows browser viewport and focused evidence panels.
It checks sidebar height, waits for loaded map tiles, and blocks API writes.
Run it against a populated local server:

```powershell
node .\scripts\capture_readme_showcase.cjs
.\.venv\Scripts\python.exe .\scripts\review_readme_images.py
.\.venv\Scripts\python.exe .\scripts\index_readme_images.py
```

The default record IDs identify the local documentation session. A fresh clone does not contain these records.
Use `EV_SHOWCASE_RUN` and `EV_SHOWCASE_RL_RUN` for compatible completed experiment records.
The binary job and PPO campaign selectors require retained local training records.
This script is an optional documentation capture, not a clean-clone verification gate.
The isolated application checks generate their own fixtures.

Inspect `artifacts/handoff/showcase/contact-*.png` and each important full-size image.
The [coverage index](SCREENSHOTS.md) records the images, evidence types, and known limitations.

## Configuration reference

```powershell
.\.venv\Scripts\python.exe .\scripts\export_configuration_reference.py
```

Check the generated table against GUI presets. A preset can override a schema default.

## Reference generation and diagnostic interfaces

| Command | Purpose |
| --- | --- |
| `python scripts/run_novi_sad.py` | Generate the complete reference workflow using the trusted local OSM cache |
| `python scripts/run_legacy_gui.py` | Open the preserved upstream GUI |
| `python scripts/run_playground_dashboard.py` | Open the Streamlit diagnostic interface |
| `python scripts/run_playground_mcp.py` | Start the stdio MCP service |

Use `.venv\Scripts\python.exe` for these commands when no environment is active.
The full reference workflow requires the ignored OSM snapshot. A fresh clone cannot reproduce it exactly without that snapshot.
Do not regenerate reference files for a documentation-only change.
A model change requires the complete workflow and consistent maps, manifests, and validation reports.

The presentation geometry exporter uses the trusted local OSM cache.
It is unnecessary for normal setup because the geometry and detailed map are already versioned.
Refresh source-document copies separately when documentation changes. Do not hand-edit generated geometry or study results.

## Local files and cleanup

Runtime catalogs include experiment definitions, results, benchmarks, trained models, and chat.
They remain on the current computer and are excluded from Git.
Published study evidence, reference JSON, configuration, and screenshot assets remain versioned.
Removal from Git tracking does not delete local runtime files or change previous Git history.
