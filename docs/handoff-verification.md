# Handoff verification

Verified on Windows on 12 September 2026.
The application documentation follows the final requested scope. Presentation documentation is not part of the application screenshot index.

## README showcase revision

The 12 September revision replaces the README's earlier full-page captures with 42 viewport and focused-panel images.
The capture uses Windows Chromium at 1440 by 960 pixels.
It waits for saved evidence and complete map tiles, checks sidebar height, and blocks API writes.
All 42 captures completed with no browser page errors.
Inspection used contact sheets and full-size map, demand, controller, handoff, review, and per-car images.

The generated banner is concept artwork. Its exact prompt and provenance accompany the assets.
The archived benchmark job remains labeled failed because its implementation changed during execution.
The binary job remains interrupted after 23 episodes. The PPO campaign remains budget-limited without a complete held-out block.
The demo remains labeled synthetic playback.

The new per-car inspector reads recorded interval states.
Browser verification selected a charging cell and confirmed its 7.4 kW power readout.
A real 20-car evaluation completed 132 intervals using a saved policy and a separate evaluation seed.
It delivered 224.985 kWh of 280 kWh requested, with 55.015 kWh unmet and zero electrical violation intervals.
These results establish an executable inspection example, not policy convergence or complete charging service.

| Revision check | Result |
| --- | --- |
| Python regression suite | 288 tests passed in 254 seconds |
| Production build | TypeScript and Vite passed |
| Screenshot workflow | 42 captures passed with no page errors |
| Isolated application workflow | 94 checks passed with 284 browser API responses |
| Local documentation links | 183 targets checked with no missing files |
| Preserved runtime files | All 599 index-removed files remain on disk |
| STE structural lint | Zero hard findings across README and revised operational guides |
| Evidence labeling | Real simulation, historical failures, and synthetic demo claims remain separate |

The STE check disables synonym-rotation warnings to preserve distinct interface command names.
Passive-voice and tense advisories received manual review. This check does not certify the official STE dictionary.
The [coverage index](SCREENSHOTS.md) links screenshots to procedures.

## Setup and start

| Check | Result |
| --- | --- |
| Clean setup in Windows PowerShell 5.1 | Passed with an explicit Python 3.11 executable |
| Repeat setup in PowerShell 7 | Passed without deleting the environment or local data |
| Python dependency consistency | `pip check` passed |
| RL imports | PyTorch 2.9.1+cpu, Gymnasium 1.2.2, and Stable-Baselines3 2.7.1 passed |
| Production build | TypeScript and Vite passed for the app and presentation |
| External-directory start | Passed from outside the repository with a path containing spaces |
| Clean-copy start | Passed on port 8526 with empty experiment and run lists |
| Default browser | Windows accepted the browser request after the readiness endpoint returned HTTP 200 |
| Presentation option | Printed the correct presentation URL and started the server |
| Ctrl+C shutdown | Stopped the attached server and released its port |
| Missing environment | Failed with a setup instruction and exit code 1 |
| Missing Python executable | Failed with exit code 1 |
| Missing Node.js | Failed with an installation instruction and exit code 1 |
| Occupied port | Failed with exit code 1 and preserved the original socket |
| Two application servers on one port | Windows exclusive binding rejected the second server |

The clean copy started without `.venv`, `web/node_modules`, `web/dist`, or a runtime catalog.
It contained the retained repository inputs and current source files.
The machine's Python launcher did not register Python 3.11. Setup correctly stopped until an explicit `-PythonPath` supplied that interpreter.
Neither setup nor ordinary start launched an experiment or training job.

Reproduce the failure and occupied-port checks with:

```powershell
.\.venv\Scripts\python.exe scripts/verify_windows_launch.py
```

See [launcher evidence](../artifacts/handoff/windows-launch.json).

## Initial handoff application and learning checks

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 288 tests passed in 238.512 seconds |
| `npm.cmd --prefix web run build` | Passed |
| `python scripts/run_api_e2e.py` | 84 checks, 252 browser responses, no browser errors |
| `python scripts/verify_handoff_training.py` | Two binary EV training episodes and a bounded PPO package check passed |
| `node scripts/verify_presentation.cjs` | Existing presentation acceptance passed with 52 slides |
| `node scripts/verify_presentation_showcases.cjs <origin>` | Passed with both populated and empty catalogs |
| `node scripts/verify_presentation_roads.cjs` | 6,480 interpolation samples on 36 closed road paths passed |

Use the repository Python executable for the Python commands above.
The unit tests include reference checksums and electrical-model assertions.
Some subprocess tests emitted resource warnings. The complete suite finished with no failing tests.
The build reported large chunks. This does not prevent the local application from starting.

The isolated real experiment used June demand, regulated operation, 12 vehicles, whole-day charging, and seed 41001.
Its 132 intervals delivered 168 kWh to batteries, with zero unmet energy and no recorded electrical violations.
The browser check inspected results, experiment editing, run management, comparison, benchmark configuration, and API error paths.
Its fixtures are generated during verification. No private saved-run directory is required.
See [application evidence](../artifacts/handoff/e2e/results.json).

Binary training changed the policy weights over two four-vehicle episodes.
The PPO dependency check executed 16 CPU training steps in CartPole-v1.
This verifies package execution. It does not represent a complete EV PPO campaign or prove controller superiority.
See [training evidence](../artifacts/handoff/rl-smoke.json).
Live Codex messages were not sent. Chat documentation keeps authentication separate from ordinary simulation.

## Documentation and retained data

The [screenshot index](SCREENSHOTS.md) links application features and states to procedures and actual Windows Chromium captures.
Earlier handoff screenshots use a 1600 by 1000 pixel viewport, with full-page captures for long forms.
The revised README uses the 1440 by 960 captures described above.
Data views wait for completed responses and chart rendering. Both capture sets include inspection contact sheets.
Map tiles need internet access. Place names on OSM tiles retain their source spelling.

The README, user guide, configuration reference, and application index passed the STE structural linter with zero hard findings.
The review disables only the `synonym-rotation` heuristic because distinct UI actions retain their actual names.
For example, validating a definition, checking a limit, deleting a run, and removing a selection have different effects.
The manual review covers passive-voice advisories, technical terms, units, captions, links, and scientific claims.
This is a structural review, not certification against the licensed ASD dictionary.

All 599 runtime files removed from Git tracking remain locally available and match the ignore rules.
There is no blanket JSON exclusion. Reference inputs, published study evidence, and attribution remain retained.
The numerical engine, model configurations, frozen study results, and detailed reference bundle are unchanged.
The Windows port-binding fix changes server startup only.
Linux launchers and the GitHub Actions workflow were removed. No hosting or saved-run bundle was added.
