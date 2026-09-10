"""Launch the EV hypothesis playground from a repository checkout."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvgrid.paths import REPOSITORY_ROOT


def main() -> int:
    dashboard = REPOSITORY_ROOT / "src" / "mvgrid" / "novi_sad" / "playground" / "dashboard.py"
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(dashboard)])


if __name__ == "__main__":
    raise SystemExit(main())
