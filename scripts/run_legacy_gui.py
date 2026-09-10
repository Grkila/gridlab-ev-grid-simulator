"""Repository checkout launcher for the original GUI workflow."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvgrid.legacy.main import main


if __name__ == "__main__":
    main()
