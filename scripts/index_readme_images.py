"""Write the documentation image coverage table from the capture inventory."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / "artifacts/handoff/showcase"
data = json.loads((folder / "coverage.json").read_text(encoding="utf-8"))
assert not data["errors"], data["errors"]
lines = [
    "# Screenshot coverage", "",
    "The current README uses actual Windows Chromium captures at 1440 by 960 pixels.",
    "Focused panel images show individual charts without a full-page sidebar.",
    "The capture checks wait for saved evidence and loaded map tiles.", "",
    "The [asset notes](../artifacts/handoff/showcase/README.md) identify source records and distinguish real, interrupted, and illustrative evidence.",
    "Runtime JSON stays local. The banner is generated concept artwork.", "",
    "## Application feature coverage", "",
    "| Feature or state | Instructions | Image |", "| --- | --- | --- |",
]
for item in data["inventory"]:
    name = item["name"]
    if name.startswith("codex-") or name.startswith("algorithm-"):
        anchor = "strategies"
    elif name.startswith("benchmark-"):
        anchor = "benchmarks"
    elif name.startswith(("ppo-", "binary-")):
        anchor = "training"
    elif name.startswith(("experiment-", "charging-", "optimization-", "demand-assumptions", "capacity-assumptions")):
        anchor = "experiments"
    elif name == "overview":
        anchor = "navigation"
    elif name == "network-loaded":
        anchor = "network"
    else:
        anchor = "results"
    label = name.replace("-", " ")
    lines.append(f"| {label} | [Procedure](USER_GUIDE.md#{anchor}) | [{name}.png](../artifacts/handoff/showcase/{name}.png) |")
lines += ["", "## Inspection and supplemental states", "",
          "All current viewport images keep the sidebar at the full viewport height.",
          "Map captures include loaded street tiles and visible OSM attribution.",
          "The benchmark dashboard intentionally shows a failed historical job with retained rows.",
          "The binary training and PPO campaign images retain their interrupted and budget-limited status.",
          "The PPO demo identifies its synthetic data on screen.", "",
          "Earlier empty, error, comparison, and advanced-form captures remain in the [supplemental inventory](SCREENSHOTS-ARCHIVE.md).",
          "Those earlier full-page images are not the current README showcase.", "",
          "Generate inspection sheets with `scripts/review_readme_images.py`.", ""]
for sheet in sorted(folder.glob("contact-*.png")):
    lines.append(f"- [Inspection sheet {sheet.stem.removeprefix('contact-')}](../artifacts/handoff/showcase/{sheet.name})")
(root / "docs/SCREENSHOTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Indexed {len(data['inventory'])} captures")
