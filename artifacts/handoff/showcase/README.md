# Application showcase assets

The PNG files show actual application states from a Windows Chromium browser.
Viewport captures use 1440 by 960 pixels. Focused panel captures show individual charts or evidence areas.
The capture script waits for data and map tiles. Viewport checks require the sidebar to fill the screen.
No screenshot contains generated charts or substituted application data.

## Evidence sources

| Record | Use and limitation |
| --- | --- |
| `run-9705783b2f734e3c` | Completed 5,000-EV whole-day experiment. Hourly map, demand, heatmap, and capacity images |
| `run-bb878beb04274b5d` | Completed 20-car binary-policy evaluation. Real per-car states with unmet energy |
| `train-c2553d19d54147af` | Interrupted binary training. Retains 23 recorded episodes |
| `ppo-f0730fea774a968c1ad4` | Budget-limited continuous campaign. No complete held-out block |
| `bench-c0c965da89ab4b2d` | Historical benchmark with 70 retained cells. Job failed an implementation-change check |

Runtime JSON stays local and ignored. These IDs document provenance, not files supplied by a fresh clone.
PPO demo curves are authored synthetic playback. Strategy handoff images show prepared, unsent requests.

## Banner provenance

`banner.png` is generated concept artwork, not a screenshot, photograph, or geographic reference.
The revised banner preserves the original composition and typography while replacing the invented arched bridge with a low, straight bridge that joins the two riverbanks. It was made with the built-in image tool in edit mode. The output is 2172 by 724 pixels.

Visual bridge and riverbank reference: [Novi Sad and Petrovaradin panorama](https://commons.wikimedia.org/wiki/File:Novi_Sad,_Petrovaradin,_pohled_na_m%C4%9Bsto_a_pevnost.jpg) by Aktron / Wikimedia Commons, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). The reference was used to guide the generated edit; the banner itself remains illustrative. Alterations: stylized rendering and bridge integration into the existing concept artwork.

Original concept prompt:

> Use case: stylized-concept. Create a polished wide GitHub README banner for the existing project GridLab, an EV charging research application for Novi Sad. Aspect ratio 3:1, 1800 by 600 pixels if possible. Dark forest green and midnight teal background with restrained lime and white accents, matching a scientific engineering dashboard. Beautiful editorial isometric illustration of a river city, an abstract distribution grid linking substations and a few electric cars at charging points. Fine glowing network lines and a subtle electricity demand curve integrated as visual motifs. Layout: very clear large typography in the left third, illustration in the right two thirds, generous empty space around words. Exact text: 'GridLab' and below it 'EV charging. Grid capacity. Shared evidence.' Small line 'NOVI SAD · EV DAYS HACKATHON'. No other text. This is a concept illustration, not a map or a screenshot. Avoid actual map claims, invented numerical metrics, corporate logos, excessive glow, tiny unreadable labels, rounded dashboard mockups and clutter. Professional cover artwork, detailed but restrained, crisp typography.

Revision prompt:

> Use case: precise-object-edit. Preserve the original GridLab banner's composition, text, colors, skyline, fortress, electric cars, substations, network lines, and demand curve. Replace only the invented double-arch bridge and nearby water/banks. Using the Novi Sad–Petrovaradin reference panorama, depict a low, straight Varadin-style bridge on plain piers crossing the Danube from the Novi Sad bank on the left to the Petrovaradin bank below the fortress on the right. Both ends must meet their banks. No arches, suspension elements, new landmarks, or design changes.

## Inspection

`coverage.json` records capture URLs and image types.
`contact-*.png` contains inspection sheets. Use full-size images to read labels and exact values.
The [feature index](../../../docs/SCREENSHOTS.md) links each image to its instructions.
