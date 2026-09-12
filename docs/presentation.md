# GridLab presentation

The presentation contains 52 English slides with speaker notes and interactive application views.
It covers the challenge, model, experiments, controller research, agent workflow, benchmarks, learning, study findings, and limitations.

## Open the presentation

Run standard Windows setup first. RL dependencies are included.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Presentation
```

The default address is [the local presentation](http://127.0.0.1:8517/presentation.html).
Use `-Port` to change the server port. Use `-NoBrowser` to print the address without opening it.

## Controls

| Control | Action |
| --- | --- |
| Left / Right, Page Up / Page Down | Previous or next slide |
| Home / End | First or last slide |
| O | Slide overview |
| N | Speaker notes |
| F | Fullscreen |
| Escape | Close panels or return control from the embedded application |
| Slide selector | Select a slide directly |
| Settings | Select a completed local run, reconnect, reduce motion, or open the detailed map |
| Lock interaction | Return navigation control from the embedded application |

The application remains interactive by default. Its buttons retain their normal behavior.
Slide navigation does not save experiments, start workers, or send messages.
Form fields keep normal keyboard input. Arrow keys outside input controls can navigate the deck.
Slide hashes support direct links and reloads.

## Fresh-clone behavior

Saved experiment results, benchmarks, and trained models are local runtime files. Git does not distribute them.
Study charts, narrative, geographic assets, and illustrative playback remain available on a fresh clone.
Embedded result views explain that a completed local run is required.
Create a run through Experiments, then select it in presentation settings.

The historical 10,000-EV run is preferred if it exists locally. Otherwise, the deck selects another completed local run.
An explicit `run` query parameter takes precedence.
No setup or presentation action automatically generates a demonstration run.

## Evidence and demonstrations

| Content | Source and interpretation |
| --- | --- |
| Main study charts | Completed direct study with frozen conditions and three seeds |
| Embedded results | Selected local run with its own assumptions and status |
| PPO demo | Clearly labeled synthetic illustration |
| MCP playback | Authored reconstruction using historical tool names and example identifiers |
| Geographic scene | OSM streets, synthetic service points, and inferred electrical routes |
| Control diagram | Proposed integration architecture, not a live utility connection |

The direct study uses a 1.02 pu source and no baseline shifting.
Its June home cases pass at sampled fleets of 13,000 immediate vehicles and 48,000 capacity-aware vehicles.
The next tested fleets, 13,500 and 48,500, fail. Each participant requests 14 kWh.
Winter baseline failures prevent annual city certification.

The full-battery selector shows an ideal energy bound, not demonstrated vehicle service.
Its 60 kWh example gives at most 24,171 full charges from the frozen June energy budget.
Local limits, extra losses, deadlines, and vehicle availability can reduce that bound.
The historical 65,544-vehicle benchmark uses different conditions and a failed final status.

The historical 10,000-EV local demonstration uses regulated operation at 1.04 pu.
Its results differ from the direct study. Do not mix their numbers or describe them as one scenario.
The MCP playback identifies its conversation as reconstructed. Click steps or tabs to navigate. It never invokes tools.

Location proposals and expansion proposals remain distinct from measured study findings.
A dedicated MV connection with its own transformer can bypass an existing residential LV branch.
It still requires investment, connection assessment, upstream capacity checks, and fresh simulation.

## Rendering and source files

English slide content and notes live in the presentation's `slides.ts` file.
Reveal.js controls slide navigation. React renders content, and Three.js maintains one geographic scene.
A persistent same-origin iframe contains the actual application.
The bridge selects views and sections. It does not provide arbitrary command execution.

The geographic scene includes 2,648 synthetic service points, inferred routes, nine primary station positions, and cached OSM road paths.
Vehicle movement follows road geometry and remains illustrative.
Reduced motion stops rotation and traffic. WebGL failure uses the SVG fallback.
The detailed map requires internet access for its OSM base tiles.

Preserve OSM/ODbL and upstream attribution. Do not infer measured buildings, traffic, or as-built feeders from the scene.
Use [developer instructions](DEVELOPMENT.md) to refresh assets and run browser checks.
The [screenshot index](SCREENSHOTS.md) covers the application.
