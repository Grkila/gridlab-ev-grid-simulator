# Windows troubleshooting

Use this guide from the repository directory unless a procedure gives an absolute path.
Keep the server terminal available. Its error message helps identify the failed operation.

## Setup cannot find Python or Node

Setup requires 64-bit Python 3.11 and Node.js 24.
An activated environment from another project does not satisfy this requirement.

1. Open a new PowerShell terminal after installing prerequisites.
2. Check the available commands.

   ```powershell
   Get-Command py.exe, node.exe, npm.cmd -ErrorAction SilentlyContinue
   py -3.11 -c "import sys,struct; print(sys.executable); print(sys.version); print(struct.calcsize('P') * 8)"
   node.exe --version
   ```

3. Confirm Python reports version 3.11 and 64 bits.
4. Confirm Node reports version 24.
5. Run setup again with the README command.

If `py` is unavailable, give setup the installed interpreter path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -PythonPath "C:\Python311\python.exe"
```

Replace the example path with the actual executable.
Do not select a Python executable from an unrelated virtual environment.

## A dependency install or build failed

Setup stops at the failed command. A partial setup cannot start the application.
Network interruptions can leave some packages installed and others missing.

1. Read the first failed command in the setup output.
2. Restore the required network connection or prerequisite.
3. Repeat setup with the same command.
4. Check the installed Python packages if setup reports an import failure.

   ```powershell
   .\.venv\Scripts\python.exe -m pip check
   .\.venv\Scripts\python.exe -c "import torch,gymnasium,stable_baselines3; print(torch.__version__,gymnasium.__version__,stable_baselines3.__version__)"
   ```

Setup includes RL dependencies. Do not use a global `pip` command to repair the repository environment.
Repeat setup preserves local saved runs and training records.
For TypeScript or source errors after an update, retain the exact error and inspect local source changes.

## PowerShell blocks the script

Use the documented `powershell -NoProfile -ExecutionPolicy Bypass -File` command.
For PowerShell 7, use `pwsh` with the same arguments.
These arguments apply to the launched process. They do not change machine-wide execution policy.
An organization policy can still restrict script execution.

## Port 8517 is occupied

The launcher reports the occupied port without stopping its owner.
Use another port:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Port 8520
```

To inspect the original listener:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8517 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Stop a previous GridLab server with **Ctrl+C** in its own terminal.
Do not terminate another application's process to free the port.

## The browser does not open or connect

The launcher waits for the server before requesting a browser window.
Keep its terminal open while the application runs.

1. Check the printed address and port.
2. Open that address manually if the browser did not open.
3. Check server readiness from another PowerShell terminal.

   ```powershell
   Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8517/api/agent-contract |
       Select-Object StatusCode
   ```

4. Use the selected port if startup used `-Port`.
5. Read the server terminal if the request cannot connect.

An HTTP 200 response confirms that the API responds.
It does not confirm that external map tiles or every saved result have loaded.

## The map is gray or incomplete

GridLab loads its topology from the local service. The street basemap uses external OpenStreetMap tiles.
A slow or blocked tile connection can leave the basemap gray while network data remains available.

1. Wait for the map tiles to finish loading.
2. Check that the browser can access the internet.
3. Reload the page once after restoring connectivity.
4. Inspect the browser Network panel if tiles still fail.

Failed tile requests identify a basemap connection problem.
Reinstalling Python or deleting saved results does not repair that connection.
The [screenshot guide](SCREENSHOTS.md) requires loaded tiles before capturing a map.

## Results take longer to load

Saved runs can contain many cases, interval measurements, and individual vehicle states.
The result screen waits for this evidence before displaying its charts.

1. Wait until the loading message disappears.
2. Check the selected run and case.
3. Use **Refresh** once if a running job has new evidence.
4. Inspect run status and the server terminal if loading does not finish.

Do not repeatedly start the experiment because a result view is slow.
Changing the result time selects a recorded interval. It does not launch a new simulation.

## Saved runs or models are missing

A fresh clone starts with empty runtime catalogs. Screenshots do not supply their underlying saved runs.
Each storage root has its own experiment, benchmark, training, and chat records.

1. Confirm that the server belongs to the intended repository checkout.
2. Check whether an explicit runtime storage override is active.

   ```powershell
   Get-Item Env:EV_PLAYGROUND_HOME -ErrorAction SilentlyContinue
   ```

3. Restore the intended launch environment if the override is unexpected.
4. Follow the first-experiment procedure if this is a new checkout.

Git ignores local runtime records. An ignored file can remain available on disk.
Do not delete catalogs to recover a missing selection.

## A run finishes but does not pass

**Completed** describes execution status. Acceptance also depends on energy service and electrical constraints.

1. Read unmet energy and pending energy.
2. Inspect voltage, line loading, transformer loading, and capacity-stage limits.
3. Inspect constraint events and solver convergence.
4. Check the saved assertions and frozen operating assumptions.

A low peak can result from insufficient charging.
A zero-EV violation indicates a baseline problem under the selected conditions.
Do not relax limits to relabel a failed case as validated.

## Training stopped or the curve looks poor

The PPO demo uses synthetic playback. Its curve is not evidence that a real model converged.
Binary training and PPO campaigns retain actual progress when available.

| Recorded state | Next action |
| --- | --- |
| Binary worker interrupted | Inspect recorded episodes and the frozen definition. Treat the job as incomplete |
| PPO budget exhausted | Inspect the campaign stage and retained checkpoints. Use **Resume checkpoints** when eligible |
| Cancelled campaign | Inspect the stop reason and available checkpoint controls |
| No complete held-out block | Keep the improvement verdict unestablished |
| High reward with unmet energy | Inspect reward components and service metrics before accepting the policy |
| Missing compatible model | Complete compatible training before selecting a learned controller |

Use separate training and evaluation seeds.
Changing reward settings during evaluation rescales the score. It does not retrain the saved policy.
See the [training procedures](USER_GUIDE.md#training) and [continuous campaign guide](continuous-rl.md).

## A benchmark is incomplete or failed

Each matrix cell has its own result. The job also has a completion status and frozen implementation identity.

| Finding | Interpretation and response |
| --- | --- |
| Time limit reached | Some trials remain unknown. Inspect the last completed trial before increasing a future budget |
| Search ceiling reached | The largest tested fleet passed. Capacity above that bound remains untested |
| Grid fails with 0 cars | The frozen baseline cannot establish EV capacity for that case |
| Implementation changed during benchmark | Retain the record, stop changing source, and start a fresh benchmark |
| Different fixture hashes | Treat comparison as descriptive until matching conditions are established |
| Green rows inside a failed job | Inspect those retained rows without claiming that the entire job completed |

Do not replace unknown values with zero or compare unmatched peaks as an algorithm ranking.
The [benchmark guide](benchmark.md) explains seeds, fixtures, search limits, and paired comparisons.

## Codex chat cannot send or implement

Ordinary experiments use the local simulator and do not need Codex authentication.
Live chat requires an installed and authenticated Codex CLI for the current Windows account.

1. Confirm that the CLI is available in a new terminal.

   ```powershell
   Get-Command codex -ErrorAction SilentlyContinue
   codex --help
   ```

2. Complete the CLI's documented authentication procedure if required.
3. Restart GridLab after changes to the command search path.
4. Inspect the chat error and server terminal if sending still fails.

Implementation requires a saved specification and explicit implementation context.
**Continue with assistant** prepares a request. It does not prove that code was written or tested.
Inspect tool details and the saved evidence before accepting a result.
Cancelling a chat response does not cancel experiments already accepted by the simulator.

## What to record for a reproducible issue

Record the command, error text, application page, selected run or job ID, and relevant version information.
Include whether the record is complete, interrupted, or budget-limited.
Keep credentials and private chat content out of issue reports.
