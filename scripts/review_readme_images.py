"""Create inspection sheets from actual documentation screenshots."""
from pathlib import Path
from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[1] / "artifacts/handoff/showcase"
files = sorted(p for p in folder.glob("*.png") if not p.name.startswith("contact-") and p.name != "banner.png")
for offset in range(0, len(files), 4):
    sheet = Image.new("RGB", (1440, 1030), "#dddddd")
    draw = ImageDraw.Draw(sheet)
    for index, file in enumerate(files[offset:offset + 4]):
        with Image.open(file) as source:
            source.thumbnail((720, 480))
            x, y = (index % 2) * 720, (index // 2) * 515
            sheet.paste(source, (x, y + 30))
            draw.text((x + 8, y + 8), file.stem, fill="black")
    sheet.save(folder / f"contact-{offset // 4 + 1:02}.png")
print(f"Reviewed inventory: {len(files)} screenshots")
