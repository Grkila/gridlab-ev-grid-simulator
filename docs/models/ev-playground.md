# EV hypothesis playground

The EV hypothesis playground runs bounded, repeatable charging experiments against a reduced Novi Sad medium-voltage planning proxy. It is suitable for screening hypotheses and finding counterexamples. It is not a utility-validated network, an operational controller, or a claim about the maximum EV hosting capacity of Novi Sad.

The [independent network-validity audit](../network-validity-independent-audit.md) still bounds the AC model: it has no physical LV feeders or MV/LV assets. The current [capacity alignment](../capacity-alignment-2025.md) adds aggregate transmission and downstream transformer/LV capacity checks with explicit editable demand-share assumptions. These checks do not calculate LV voltage or individual asset loading.

## Architecture and model boundary

The active reduction has 76 buses, 58 lines, 12 transformers, 42 demand blocks and ten charging hubs across six source areas. NS1, NS6 and FUT supplies are removed; their 492 demand members are reassigned to retained 20-kV feeder equivalents. All 2,648 demand members and 100% of city demand remain. MV delivery capacity is balanced to 299 MW at 20 kV and 179 MW at 10 kV. See [capacity alignment](../capacity-alignment-2025.md).

Each case gets a fresh pandapower network and one constant-PQ power flow per 15-minute step. Cars are represented as aggregate constant-PQ demand at delivery nodes. Residential and workplace sessions use regular delivery blocks; public sessions use dedicated hubs.

The map uses an OpenStreetMap background for orientation. Displayed electrical links are a planning-model representation, not mapped as-built cable routes. The detailed reference model remains separate. An optional `detailed_check` can replay selected snapshots there; normal dashboard and MCP runs use the experiment network.

The baseline generator cyclically interpolates a selected 24-hour seasonal shape to 96 quarter-hour average-kW values. It converts monthly energy to kWh, divides by `days_per_month`, normalizes the curve so `sum(kW) * 0.25 h` equals daily energy, and repeats it for the requested days. `lower` and `upper` apply deterministic -2.9% and +2.9% factors. With `scope: city_total`, the model scales this city input by the retained-demand fraction because excluded source shares are not redistributed in explicitly reduced variants. The default whole-city model has fraction 1.0, so city demand is not reduced. That fraction uses the original calibrated-MW source shares. Use `scope: active_sources` when the energy already describes only retained sources.

Land-use mixtures create residential, commercial, and industrial block shapes. `preserve_city` normalizes blocks at every interval, so their sum is the original city curve. A global composition override therefore redistributes demand between blocks but its common temporal factor cancels during interval normalization. `preserve_energy` retains the altered aggregate shape and scales it once to conserve horizon energy.

Each vehicle gets one seeded session per simulated day. A completed run extends beyond the nominal demand horizon through the last generated departure. No new sessions are added in this tail. Pending energy is measured at the actual result horizon (including an early stop); departure shortfalls count only deadlines already reached.

## Experiment contract

### Estimated district capacity and car placement

The user-selected simplification keeps the existing small pandapower network and omits individual MV/LV assets. Thirteen delivery districts group existing demand blocks and charging hubs by their supplying delivery station. These are electrical study groups, not verified municipal district boundaries. Each district has an aggregate kW budget checked separately from the pandapower line and upstream-transformer constraints. All blocks and hubs in a district share that budget. A district violation does not disconnect a physical network asset.

`district_capacity.scenario` selects `low`, `central` or `high`. Central budgets use full aligned MV delivery ratings (478 MW combined). The last 25% is usable reserve, not withheld capacity. Low/high scale district estimates by 0.8/1.2 as sensitivity cases; upstream and aggregate stage constraints still apply independently. Overrides retain provenance and scenario scaling.

Override a district's central estimate with `district_capacity.overrides.<id>.capacity_kw` and a nonempty `provenance` explanation. The selected scenario factor applies to overrides too. A value entered in the GUI is therefore a central estimate, not an already-scaled limit. The live catalog lists accepted district IDs and source assignments; unknown or excluded IDs are rejected. Resolved estimates and their provenance are frozen in run records. Historical runs without this information have no district-capacity verdict.

`fleet.district_mix` optionally sets district allocation probabilities summing to one. For example `{NS5: 0.7, TELEP: 0.3}` places cars only in those districts. Seeded sampling is reproducible; finite-fleet observed percentages can differ from the requested probabilities. Within the selected district, the residential/workplace/public charging mix still determines session behavior and eligible blocks. Leaving the district mix null preserves automatic allocation. Source connections and land-use mixtures remain separate.

At each 15-minute interval, district demand is the sum of baseline plus allocated EV charging power over its blocks. The saved district record reports capacity, remaining headroom, percentage loading and vehicle counts. `district_capacity_exceeded` means this aggregate demand exceeded the estimated kW capacity. The event stops an ordinary run and preserves incomplete counterexample evidence. Use `max_district_loading_percent` or `district_overload_steps` for district assertions. Upstream transformers are still checked independently: multiple districts may fit their own budgets while overloading a shared source.

Unmanaged charging is not clipped to these budgets. The capacity-aware strategy shares district headroom across all connected blocks and hubs, alongside its existing block/source budgets and AC checks. Baseline demand already exceeding a budget remains a violation even when EV charging is reduced to zero. See [district example](../examples/district-capacity.yaml).

Inputs use a strict Pydantic schema: unknown fields, invalid ranges, NaN, and infinity are rejected. See the [exported schema](../examples/ev-playground.schema.json). Agents should start with the live MCP catalog because it reports the installed contract.

Implemented strategies include `immediate`, `fixed_delay`, `randomized_delay`, `capacity_aware`, `least_laxity_first`, `valley_filling`, `mpc`, `voltage_responsive`, and `rl`. See [strategy development](../strategy-development.md) for controller assumptions and standardized workflow commands. `fleet_sizes` is the only numerical sweep; cases are the product of fleet sizes, seeds, and strategies. Change other parameters through a saved revision. `stress_first` changes order, not membership.

Hard assertions apply `le` or `ge` to an absolute case metric. Paired assertions compare candidate and control city peaks by a required reduction. Only completed runs can pass, and missing electrical results cannot satisfy electrical assertions. By default, `stop_on_violation: true` stops the run at the first district or upstream-transformer violation and records `stopped_on_violation`; its partial evidence remains incomplete and cannot support paired comparisons. Set it to `false` explicitly for full-horizon overload studies or strategy comparisons.

`metric_boundary`, `observation_contract`, and `case_origin` are interpretation/provenance metadata; they do not change calculations. `random` and `ga` origins label externally produced cases. Random search, genetic algorithms and reinforcement-learning controllers are not implemented. The simulator reset/step interface permits later controller adapters.

### Minimal comparison

```yaml
schema_version: 1
name: Evening delay comparison
hypothesis: Fixed-delay charging reduces the city peak by at least 3%.
metric_boundary: city_total
case_origin: manual
fleet: {fleet_size: 200}
strategies: [immediate, fixed_delay]
seeds: [1, 2]
stop_on_violation: false
assertions:
  - type: paired
    metric: peak_demand_kw
    reduction_fraction: 0.03
    control: immediate
    candidate: fixed_delay
```

### Fleet-size sweep

```yaml
name: Capacity-aware fleet sweep
hypothesis: Capacity-aware charging stays within the planning limits.
metric_boundary: grid_asset
case_origin: llm
demand: {monthly_energy: 95636, unit: MWh, month: 1, days: 1, variation: upper}
fleet: {fleet_size: 0, charger_kw: 7.4, energy_kwh: 14, efficiency: 0.9}
strategies: [capacity_aware]
seeds: [1, 7]
fleet_sizes: [0, 100, 500]
stop_on_violation: false
assertions:
  - {type: hard, metric: min_voltage_pu, operator: ge, value: 0.95}
  - {type: hard, metric: overload_steps, operator: le, value: 0}
```

### Composition scenario

```yaml
name: Commercial-heavy district monitor
hypothesis: The monitored district and its upstream transformer stay within limits.
metric_boundary: grid_asset
demand:
  month: 7
  days: 2
  composition: {mode: preserve_energy, residential: 0.35, commercial: 0.55, industrial: 0.10}
fleet: {fleet_size: 100}
strategies: [immediate]
seeds: [1]
# stop_on_violation defaults to true for this monitoring run.
assertions:
  - {type: hard, metric: overload_steps, operator: le, value: 0}
assumptions:
  - Demand shapes are user-supplied seasonal hourly profiles.
  - The commercial-heavy mix is a chosen scenario, not an observed forecast.
```

## Interfaces and operation

Run the dashboard or local stdio MCP server from the checkout:

```powershell
npm --prefix web ci
npm --prefix web run build
.\.venv\Scripts\python.exe scripts/run_playground_app.py
.\.venv\Scripts\python.exe scripts/run_playground_mcp.py
```

The MCP exposes catalog, validation, immutable save/revision, start/resume/cancel, status, results, and comparison tools. It accepts declarative inputs only, not arbitrary Python. The [notebook](../examples/ev_playground.ipynb) demonstrates direct Python use. Detailed checks are explicit: import `detailed_check` from `mvgrid.novi_sad.playground.detailed` and pass completed reduced results and selected steps. Do not describe normal runs as detailed checks.

Definitions are content-addressed and immutable. Run manifests freeze definitions, seeds, source/input hashes, and dependency versions. Interrupted or runtime-limited matching runs can resume without mixing fingerprints. `ev_add_cases` creates a revision and replaces each supplied top-level field in full.

## Evidence and limitations

Research-supported principles motivate time-varying demand, controlled charging comparisons, voltage and thermal checks, and reproducible scenarios. See [methodology](../methodology.md), [data sources](../data-sources-and-licenses.md), and the [Novi Sad model](novi-sad.md). These sources and synthesized findings support study design; they do not validate the inferred network against utility records.

The seasonal profiles are user supplied. Charging windows, land-use archetypes, efficiency, charger rating, feeder parameters, aggregation, and scenario composition are assumptions. The experiment-network representation, immutable manifests, bounded matrix, single worker, and explicit completion states are engineering decisions.

Topology counts and benchmark values must be taken from the current generated [model_validation.json](../../artifacts/playground/evidence/model_validation.json). Regenerate that record after topology changes before quoting its values. A comparison with the detailed model is diagnostic, not calibration or full validation, and measured timings are not performance guarantees.

Recorded backend acceptance covers 42 tests, all ten MCP tools over stdio, stress-order replay, overnight completion tails, runtime-budget terminal state, and rejection of unknown electrical intervals as passes. The final compiled React dashboard is checked separately from the legacy Streamlit diagnostic interface. See [testing.json](../../artifacts/playground/evidence/testing.json) and [acceptance review](../acceptance-review.md) for the current gate status.

The subsequent district-capacity extension passed 52 tests and the expanded actual MCP lifecycle, including a district counterexample and district-specific car placement. [District acceptance evidence](../../artifacts/playground/evidence/district-capacity.json) records exact GUI-to-result comparisons and the current implementation/build hashes. The separate [scope review](../district-capacity-review.md) tracks reviewer corrections and final acceptance. The notebook's district section was executed with a text display adapter and a noninteractive plotting backend; that checks code execution, not an installed Jupyter kernel.

The parent agent exercised the compiled React GUI: presets, invalid-definition rejection, YAML import, saving and running experiments, cancellation/resume, stopped-run counterexamples, comparisons, map/car popups, clock navigation and live Codex MCP chat. A separate testing agent checked saved/API values against those observations; its browser tools were unavailable. The last browser regression checks switching a one-interval stopped result to a full result without duplicate heatmap ticks. [Browser evidence](../../artifacts/playground/evidence/react_browser.json) records this provenance. Export was triggered, but the downloaded file contents and plugin pickup in a brand-new Codex desktop task were not verified.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/verify_playground_dashboard.py
.\.venv\Scripts\python.exe scripts/verify_playground_mcp.py
```


## Green GUI and Codex chat

Compare runs uses individually labeled checkboxes: select 2–8 runs, then choose **Compare selected**. No Ctrl/Shift selection is required. The interface shows loading and request errors, clears stale output when selection changes, and includes display names in the result table. Completed runs with incompatible saved inputs or implementation versions remain available for descriptive comparison; incomplete runs are explicitly labeled partial. Neither is presented as a controlled paired result.

All application tabs share the same compact layout, panel spacing, typography, form controls, tables, focus styling, and floating chat. `web/src/system.css` applies common interface rules; `web/src/results.css` contains shared foundations and Results-specific components. Overview uses a concise study introduction instead of a promotional hero. The mobile navigation fits all five sections, including RL workspace. Notifications expose live status and a keyboard-accessible dismiss button; a skip link and named chat controls support keyboard and assistive-technology users.

Vercel's `web-design-guidelines` skill was installed into the local Codex skills directory on 2026-09-10, and its current interface guidelines informed this consistency pass. Desktop/mobile visual checks and experiment validation passed. The frontend build and the 72-test suite passed; RL training itself was not launched as part of this design check.

Results opens the most recent run and groups its contents into Summary, Network, Districts, and Evidence. A shared 15-minute timeline and previous/next controls retain the selected interval between views; chart markers identify that interval. Summary shows city demand and vehicle counts, Network contains the map and heatmap, Districts pairs delivery and transformer charts, and Evidence holds frozen capacity assumptions and assertions. Detailed measurements, run management, and comparisons expand on demand. Safety-stop warnings remain visible in every view. Total interval demand is displayed in MW; EV demand and chart series retain kW.

The Results redesign applies [Anthropic's frontend-design guidance](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md), consulted on 2026-09-10. Browser verification covered desktop and mobile layouts, shared time navigation, district selection, measurement disclosure, and stopped-run warnings; the React build and 62 repository tests passed.

In Results, select a run to edit its display name with **Rename run**, or remove a finished run with **Delete run**. **Undo delete** restores the last removed run while the page remains open. Deletion hides the run from the catalog and evidence APIs; it does not erase its files. Display names and deletion markers are stored separately from frozen simulation evidence. Active runs must stop before deletion. The restore API remains available after a page reload.

The chat launcher does not pin a model and passes `--ignore-user-config`; it uses the installed CLI's resolved default. A local launch with the same model-selection flags on 2026-09-10 reported `gpt-6-astra` (Codex CLI 0.153.4). A future CLI default may differ.

The primary GUI is a local React application at http://127.0.0.1:8517. It calls the same Python `Service` used by MCP and the notebook. The older Streamlit launcher is retained as an optional diagnostic interface. The React time axes display HH:MM clock time with day prefixes beyond midnight; simulation cells remain 15 minutes wide. Some legacy Streamlit diagnostic axes use elapsed hours.

The chat uses a native `codex exec --json` process, the user's existing Codex authentication, and the local MCP server. Observable tool calls and responses are displayed from actual CLI events. Chats persist under the same runtime directory. Each turn supplies recent conversation history to an ephemeral CLI invocation; a 180-second limit bounds a turn. The app isolates the CLI from unrelated user-configured integrations with `--ignore-user-config` and uses a read-only shell sandbox; experiment mutations occur through the explicitly configured local MCP. It does not ask for or store an API key. `EV_CODEX_EXECUTABLE` can identify a native Codex executable on another installation.

The HTTP server binds only to loopback and rejects external Host/Origin values and non-JSON mutations. It is a local single-user application, not a hosted multi-user service. Chat cancellation stops the chat process; a simulation already started through MCP is cancelled separately from the run controls.

Implementation references: [Codex non-interactive mode](https://developers.openai.com/codex/non-interactive-mode) and [Codex MCP configuration](https://developers.openai.com/codex/mcp). The installed CLI help was also checked against the actual invocation. Live tool-call evidence is in `artifacts/playground/evidence/codex_chat.json`.


### Calibrated seasonal presets

The coordinated study supplies January at 120,000 MWh over 31 days and June at 76,000 MWh over 30 days. Four example YAML files cover winter/summer base/worst-case. `annual_growth_rate: 0.03` compounds as `(1 + rate) ** years_ahead`; no baseline calendar year is assumed. `scenario: worst_case` multiplies baseline demand by 1.20 on every simulated day (the presets use a one-day horizon), independently of EV charging. These presets reset `variation: base`; explicitly combining `upper` with `worst_case` also applies the legacy 1.029 sensitivity factor. Source exclusion scaling is applied afterward.

Chat-launched simulations are submitted through the app's loopback run broker. The long-lived GUI process owns each simulation worker, so it survives the short-lived Codex CLI turn. The MCP and broker must reference the same runtime directory. A stopped or interrupted run still requires explicit inspection or an eligible resume; it is never silently restarted as a success.

### Aggregate capacity stages and usable reserve

The dashboard accounts for the image's 1,178 MW infrastructure sum through five successive/parallel stages. New runs check transmission (430 MW), 20/10 kV delivery (299/179 MW), assumed downstream transformers (150 MW) and LV distribution (120 MW). Reserve use begins at 75%; the limit is 100%. `network_capacity.lv_baseline_fraction` and `lv_ev_fraction` select the LV share, defaulting to 0.5 and 1.0. See [the model interpretation and reproduction guide](../capacity-alignment-2025.md).

RL numeric editors preserve editable text separately from numeric API values: clearing required fields leaves them empty and invalid; clearing the optional energy budget disables it. Decimal typing is preserved, and initial catalog loading cannot replace an edited training draft. GUI regression coverage: keyboard clear and decimal entry, reward editing, optional budget clearing, catalog refresh, and tab navigation.

## Comparison failure isolation

Multi-strategy batches attempt every selected case even when an earlier case stops at a grid limit, fails a hard assertion, or raises a controller error. `stress_first` orders those cases without rejecting the rest of the comparison. Explicit cancellation and the shared runtime budget still end the batch. Single-strategy early-stop behavior is preserved.

The GUI defaults multi-strategy selections to `stop_on_violation: false` for full trajectories. If the user explicitly enables early stopping, each affected case records its prefix and the next strategy still runs. Error cases store an error and missing metrics, not zero-valued successful results. A completed batch can therefore have a failed or incomplete verdict. Such cases cannot establish a successful paired comparison. Existing saved definitions and historical results are unchanged.

Verification: eight independent worker regression tests plus real two-strategy electrical runs in `artifacts/playground/evidence/comparison_continuation.json` (one interval per case with early stopping, 96 per case with full-horizon evaluation, both preserving failed assertions).


Chat recovery, cancellation, conversation history, pinned constraints, evidence retention, and paginated MCP results are documented in [Chat and MCP reliability](../chat-mcp-reliability.md).
