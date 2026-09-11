# Novi Sad MV grid planning model

This Schneider challenge repository builds a single geo-referenced, nine-source medium-voltage planning model for Novi Sad from OpenStreetMap-derived study data. It produces a pandapower network, an interactive map, and an internal validation report from the same inferred topology.

The current reference model passes its internal consistency gate with 2,648 loads, 21,783 buses, 21,759 lines, nine radial source islands, a 0.9568 pu minimum voltage, 72.29% maximum line loading, and 88.33% maximum transformer loading. These are synthetic planning results—not utility measurements or an as-built network.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/mvgrid/novi_sad/` | Deterministic Novi Sad generation, modelling, mapping, and validation pipeline |
| `src/mvgrid/legacy/` | Original GUI-oriented OSM reconstruction implementation |
| `scripts/` | Launchers that work directly from a checkout |
| `configs/` | Novi Sad configuration and Darmstadt example |
| `data/novi_sad/reference/` | Versioned reference inputs and intermediate data |
| `data/cache/` | Ignored local OSM/pickle caches |
| `artifacts/novi_sad/reference/` | Reference model, map, results, and reports |
| `docs/` | Architecture, methodology, provenance, and reproducibility notes |
| `.agents/` and `AGENTS.md` | Durable project context and working rules for coding agents |

## Setup

Python 3.10 or 3.11 is recommended. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

The editable install reads the pinned runtime dependencies from `requirements.txt`, including GeoPandas; do not install a second conflicting version over them.

### Quick start on another Windows computer

Install [Python 3.11](https://www.python.org/downloads/) and [Node.js](https://nodejs.org/), clone this repository, and run the following commands in PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
npm --prefix web ci
npm --prefix web run build
.\.venv\Scripts\python.exe scripts/run_playground_app.py
```

Open `http://127.0.0.1:8517` if the browser does not open it automatically. After the first setup, only the final command is needed to start the application again. The simulator and presentation work without an OpenAI API key. The optional in-app chat additionally requires an installed and authenticated Codex CLI; it uses that user's existing Codex authentication.

The application is intentionally local and single-user: its server listens only on `127.0.0.1`. Do not expose it directly to a public network. To update an existing checkout, stop the application, run `git pull`, repeat `npm --prefix web ci` and `npm --prefix web run build`, and refresh the editable Python installation if `requirements.txt` or `pyproject.toml` changed.

### Quick start on Linux

On Ubuntu or Debian, install the system prerequisites and clone the repository:

```bash
sudo apt update
sudo apt install python3 python3-venv nodejs npm git
git clone https://github.com/Grkila/EV-days-chneider-challenge.git
cd EV-days-chneider-challenge
chmod +x setup.sh start.sh
./setup.sh
./start.sh
```

If the browser does not open automatically, visit `http://127.0.0.1:8517`. The setup script accepts Python 3.10 or 3.11, creates an isolated `.venv`, installs the pinned Python dependencies, installs the exact frontend dependencies from `web/package-lock.json`, and builds the production interface. Later starts only require `./start.sh`.

These commands work directly on distributions whose `python3` is Python 3.10 or 3.11, such as Ubuntu 22.04 or Debian 12. Ubuntu 24.04 ships Python 3.12 by default, so install a parallel Python 3.11 environment before running `setup.sh`. Other Linux distributions can use the same scripts after Python 3.10/3.11, the matching `venv` module, Node.js, and npm are installed through their package manager. The optional in-app chat requires a separately installed and authenticated Codex CLI on that Linux account.

This is deliberately a checkout-oriented application, not a standalone wheel: configuration, data, and artifact paths live beside the source. Use an editable install from a clone. A non-editable installation fails with an actionable message unless `MVGRID_ROOT` points to a valid checkout.

On POSIX shells, activate with `source .venv/bin/activate`; all later commands use the same forward-slash script paths shown below.

## Run

Run the unified workflow from any working directory:

```powershell
python "C:\path with spaces\to\repo\scripts\run_novi_sad.py"
```

For a quick regeneration that leaves the existing HTML map and validation reports unchanged:

```powershell
python scripts/run_novi_sad.py --skip-map --skip-validation
```

`--refresh-osm` deletes the ignored local snapshot and downloads current OSM data. Results may change as OSM changes. The normal cached run requires `data/cache/data.pkl`; that file is intentionally untracked because pickle is unsafe to accept from untrusted sources and is not a portable interchange format.

Run the original upstream GUI with:

```powershell
python scripts/run_legacy_gui.py
```

## EV hypothesis playground

The local EV playground runs bounded, reproducible charging-strategy experiments through a Streamlit dashboard or typed stdio MCP interface. See the [implementation and user guide](docs/models/ev-playground.md), [example notebook](docs/examples/ev_playground.ipynb), and [exported JSON schema](docs/examples/ev-playground.schema.json).

```powershell
.\.venv\Scripts\python.exe scripts/run_playground_dashboard.py
```

## Validate

```powershell
python -m unittest discover -s tests -v
python scripts/run_novi_sad.py
```

The committed report is at [`artifacts/novi_sad/reference/reports/novi_sad_validation_report.md`](artifacts/novi_sad/reference/reports/novi_sad_validation_report.md). Model assumptions and acceptance criteria are in [`docs/models/novi-sad.md`](docs/models/novi-sad.md).

`artifacts/novi_sad/reference/reference_manifest.json` records OS-independent, LF-normalized SHA-256 hashes and sizes for every text file in the complete reference bundle. The offline tests reject missing, mixed, or modified bundle files.

## Reproducibility and data

The versioned input manifest records the local snapshot hash and package versions, but the ignored pickle means a fresh clone cannot reproduce the reference artifacts bit-for-bit. See [`docs/reproducibility.md`](docs/reproducibility.md) before making reproducibility claims.

OpenStreetMap-derived data is attributed to OpenStreetMap contributors and is subject to the ODbL. EDS planning values retain their source-specific terms. See [`docs/data-sources-and-licenses.md`](docs/data-sources-and-licenses.md). The MIT license in this repository covers the code, not every external dataset.

## Upstream project

This work adapts the original “Automated Generation of geo-referenced MV Grid Models based on OSM Data” implementation. Its methodology is described by Tobias Gebhard, Andrea Tundis, and Florian Steinke in [Automated Generation of Urban Medium-voltage Grids using OpenStreetMap Data](https://doi.org/10.1109/ISGTEUROPE62998.2024.10863461). Original attribution is preserved in [`CONTRIBUTORS.md`](CONTRIBUTORS.md).

Contributions should follow [`CONTRIBUTING.md`](CONTRIBUTING.md).

The primary playground GUI uses a green React interface with a local Codex CLI chat. Build it with `npm --prefix web ci` and `npm --prefix web run build`, then run `python scripts/run_playground_app.py`. See the [playground guide](docs/models/ev-playground.md) for scoped demand, safety stops and chat behavior.

The **RL** workspace trains centralized on/off charging policies on randomized days,
with editable reward weights and power/energy constraint handling. Saved models
can be compared with other strategies on held-out seeds and inspected through
reward charts and charger timelines. See the [RL guide](docs/models/ev-rl.md);
the included short training demonstration is not a validated control policy.

The **Strategies** workspace provides a research-linked controller library and standardized proposal/specification/build/comparison commands. See [strategy development](docs/strategy-development.md) for the four new controller adaptations, shared RL integration and verified evidence.

The **Benchmarks** workspace compares registered algorithms on ten frozen scenarios, including citywide and single-district capacity, worst-day demand, and electrical headroom at a shared passing fleet. See the [benchmark protocol](docs/benchmark.md) for reproducibility, GUI usage and the limits of capacity estimates.
