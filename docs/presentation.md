# GridLab presentation

The presentation follows: challenge, modelling approach, repeatable experiments, algorithm development, the five answers, simulation improvements and conclusions. It contains 50 slides. Serbian copy and speaker notes are in `web/src/presentation/copy.sr.ts`; structure and the expanded simulator, LLM/MCP, benchmark and RL sections are in `web/src/presentation/slides.ts`.

## Open

```powershell
npm --prefix web run build
.venv/Scripts/python.exe scripts/run_playground_app.py --port 8507
```

Visit `http://127.0.0.1:8507/presentation.html`. The app sidebar also links to it. Vite development uses the same `/presentation.html` entry and proxies `/api` to port 8507.

Use arrow keys or the navigation buttons; O opens the overview, N opens speaker notes, F requests fullscreen. Settings selects the saved run, refreshes the backend connection, toggles reduced motion and links to the detailed map. The verified demo run is selected initially, falling back to another completed run if unavailable; an explicit `run` query parameter takes precedence. Slide hashes support direct links and reloads. Desktop landscape is the intended presentation format.

The application is interactive by default. **Zaključaj prikaz** temporarily locks interaction; Escape also returns to slide control. Arrow keys outside form fields continue navigating the presentation. Navigation itself never saves an experiment, starts a worker or sends an assistant message. Explicitly clicking application actions still uses the normal application behavior.

## Integration

Reveal.js owns slide navigation and overview. React owns content and the surrounding controls. One Three.js renderer owns the persistent city scene. One same-origin iframe owns the real application and stays mounted between slides. A narrowly scoped bridge accepts cues only from its same-origin parent when `present=1` is set. Cues select an existing app view, experiment stage, result section or strategy section and optionally open the assistant. No command-execution bridge is provided.

The presentation is a separate Vite entry so normal app startup does not load Reveal or Three.js. It uses the existing backend for live views. If the backend is unavailable, it shows an explicit reconnect screen while the narrative and study charts remain usable. If WebGL is unavailable, the geographic scene falls back to SVG. External fonts have local system fallbacks. The bundled detailed Folium map requires a network connection for its OSM base tiles; the 3D scene uses bundled geometry.

## Evidence and geography

The main numeric findings use `artifacts/challenge-study-v2/report-final.md`, the completed direct study. June home-charging sampled bounds are 13,000 immediate and 48,000 capacity-aware across three seeds; next sampled failures are 13,500 and 48,500. Primary operation is 1.02 pu with no baseline shifting. Winter baseline invalidity prevents annual certification. These figures are separate from the selected live run and from the provisional historical benchmark.

The report's frozen location windows differ from the newer whole-day app profile. New profile capacities require new completed evidence. The RL showcase remains labelled Demo data and does not establish controller superiority. Development acceleration is explained through reuse and automation; no measured development-speedup claim is made.

`scripts/export_presentation_geography.py` exports 2,648 synthetic service points, 21,753 inferred route features and nine primary station positions from existing reference data. It also copies the detailed interactive map and source documents into `web/public/presentation/`. Run this exporter before rebuilding when source data or documents change. Service-point columns are symbolic, not surveyed buildings; vehicle speeds and positions are illustrative. Vehicles follow 36 closed paths on the cached directed OSM street graph, with 31,021 unique road geometries. Cars use arc-length interpolation rather than splines, so turns remain on road segments. The whole city gently rotates and stays behind every slide; reduced motion stops rotation and traffic. The detailed geographic model is distinct from the reduced experiment network. OSM/ODbL and upstream attribution remain in the deck and source data.

## Checks

`scripts/verify_presentation.cjs` uses Playwright against the running local production server. It rejects backend mutations and checks slide layouts, persistent iframe identity, stage navigation, keyboard forwarding, overview, notes, reduced motion, deep links, source availability, mobile overflow and disconnected-backend behavior. Screenshots and its report go under `artifacts/playground/evidence/presentation/`.

The deck uses pale text on dark green, dark text on pale lime controls, and dark green backgrounds for white-labelled embedded app buttons. The acceptance script checks the principal text/control palette against a 4.5:1 contrast floor; visual inspection remains necessary over the geographic scene.

```powershell
$env:NODE_PATH = 'C:/Users/Dusan/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
node scripts/verify_presentation.cjs
```

## Serbian revision and agent demonstration

The 2026-09-11 revision shortens slide copy, adds animated exact-value counters, a simultaneous-charging chart, and a matched-policy peak chart. Counters restart on entry and finish at the cited study values; reduced-motion mode displays final values immediately. Animation is a reveal of existing data, not simulated live computation.

The LLM/MCP chapter explains capabilities, tool routing and the development workflow. The chat demonstration is prepared local MCP playback with selectable history and tool details, with no sending or execution. Chat labels are localized only inside the presentation; the ordinary app retains its existing language.

`node scripts/verify_presentation_roads.cjs` validates all closed paths against exported street segments, samples 6,480 interpolated positions and checks loop continuity. `scripts/verify_presentation.cjs` additionally checks prepared tool playback without backend writes, Serbian number formatting, exact final counters and the persistent city background.

## Prepared demonstrations

The ordinary Results page and presentation prefer `run-3484553ec8bb4a5f` (experiment `exp-bf08b8697388a90cc36f`) when no run was explicitly selected. This is a real completed 132-interval, four-controller June home-only run with 10,000 EVs and seed 41001. It uses the application's regulated assumptions (1.04 pu and energy-preserving baseline regulation), distinct from the frozen direct study's 1.02 pu assumptions. All four deliver 140,000 battery kWh with zero unmet energy. Immediate and capacity-aware peak at 182.628 MW; randomized delay at 145.407 MW; fixed delay at 201.596 MW with eight aggregate capacity violation intervals. No assertions were attached, so its recorded verdict is `evaluated_no_assertions`, not an asserted scientific pass. The full evidence is unchanged.

`scripts/prepare_presentation_demo.py` uses the current local stdio MCP contract to save and execute this demonstration. The connected older MCP instance lacked the current charging-profile schema; the launcher uses repository code. Keep its stdio session alive until the worker finishes on Windows. An initial interrupted startup (`run-f33656c46f404c1d`) is retained and is not a default.

Chart requests use `?detail=charts`: all intervals, aggregate vehicle counts, electrical states, constraints and metrics remain, while unused per-vehicle traces are omitted for non-RL cases. RL keeps its full action evidence. The default API response still exposes full records. Cases are read and reduced one at a time to bound memory. This changes transport, not calculation or evidence storage.

The network fits its actual node bounds and resizes with its panel. Presentation results initially select peak EV demand; time and strategy controls remain interactive. Bright yellow cars follow road segments; cyan pulses and a lit marker illustrate a charging stop. This scene is illustrative, separate from saved simulation intervals. The city gently turns and drifts behind slides. Text components have staggered entrance and fade/exit transitions, with reduced-motion support.

Benchmark setup, saved matrix and selection criteria have separate slides. Historical benchmark failure/incompleteness remains visible; it does not establish an overall winner. The capacity-aware explanation is scoped to the direct study's daily-fleet comparison; randomized delay has the lower matched-fleet peak. PPO animation uses explicitly synthetic demo fixtures; real PPO campaigns and completed binary REINFORCE training are separate views. Navigation starts neither training nor benchmark jobs.

The simulator slides explain Python/pandapower, 15-minute balanced AC/PQ steps, synthetic geography and sessions, and missing LV/phase/transient detail. Selected detailed replay already exists. Replacing the full simulation backend requires an adapter and fresh validation; it is a future extension, not a working one-click switch.

`node scripts/verify_presentation_showcases.cjs` checks populated showcase views, the default run, network framing, peak interval selection and absence of backend writes.

The algorithm research chapter (`researchSlides.ts`) includes baseline provenance, sLLF/ODC/voltage adaptations, historical MPC, REINFORCE and PPO references. Its Schneider comparison is explicitly conceptual, without a claim that EcoStruxure EV Charging Expert implements ODC. See docs/presentation-algorithm-research.md.

The assistant and chat-demo slides now use MCPDemo local playback, replacing the live chat demonstration. Six click-only steps show an authored prompt, contract/catalog lookup, ev_save_experiment arguments, run lifecycle, a separate comparison request and saved result. The conversation is explicitly reconstructed, not an actual LLM transcript; IDs and metrics refer to the prepared 10,000-EV demo. The Codex variant presents the project plugin and local MCP path without requiring the web application. No playback action sends a chat message or invokes a tool. Previous, next, direct history selection and reset controls are supported. No timed advancement.

Question 1 now distinguishes full-battery equivalents over 24 hours from simulated 14-kWh daily participants. The interactive 40/60/80-kWh selector uses scripts/presentation_daily_energy.py and frozen June demand. The 60-kWh result (24,171) is explicitly an ideal aggregate-energy upper bound, not demonstrated service capacity. The slide includes actual 48,000-car cohort counts and explains the provisional 65,544-car historical benchmark. See docs/presentation-daily-energy.md.

The duplicate Codex playback slide was removed. One chat-demo slide now names chat, Codex and terminal access through the project plugin; the same local playback demonstrates all entry points.

The single MCP demo has three manually selected tabs: tool history, an actual chat-panel capture with an unsent prompt, and the actual strategy-development form. GUI screenshots are static assets captured from the local application; clicking tabs performs no API writes. Manual-only timing, all GUI assets and layout were verified in the browser.

Q2 and Q4 now default to concise location-based charging and infrastructure proposals; click Results of study to inspect the preserved numerical charts. Night00-06 is an optional feasible window, not simultaneous release or a full-battery promise. Workplace dwell and managed charger availability provide scheduling flexibility. Dedicated MV supply may relieve an existing residential LV branch, but new transformation, connection assessment and upstream limits remain. This is a proposed topology change, not a finding from the current all-EV-at-LV study. The current simulator checks modeled equivalents/aggregate limits every15min, not every real transformer. Both proposal/evidence tabs and layout passed browser checks. Load-management reference: https://www.se.com/au/en/product-subcategory/1840-evlink-energy-management/ .
