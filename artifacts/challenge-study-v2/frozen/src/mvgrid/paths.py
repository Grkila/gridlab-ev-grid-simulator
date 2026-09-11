"""Stable repository paths, independent of the process working directory."""
from __future__ import annotations

import os
from pathlib import Path


_checkout_root = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(os.environ.get("MVGRID_ROOT", _checkout_root)).expanduser().resolve()
if not (REPOSITORY_ROOT / "configs" / "novi_sad.json").is_file():
    raise RuntimeError(
        "mvgrid requires a repository checkout with configs and data; install it "
        "editable or set MVGRID_ROOT to a valid checkout"
    )
CONFIG_DIR = REPOSITORY_ROOT / "configs"
DATA_DIR = REPOSITORY_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
NOVI_SAD_DATA_DIR = DATA_DIR / "novi_sad" / "reference"
NOVI_SAD_INPUT_DIR = NOVI_SAD_DATA_DIR / "inputs"
NOVI_SAD_GENERATED_DIR = NOVI_SAD_DATA_DIR / "generated"
NOVI_SAD_ARTIFACT_DIR = REPOSITORY_ROOT / "artifacts" / "novi_sad" / "reference"
NOVI_SAD_MODEL_DIR = NOVI_SAD_ARTIFACT_DIR / "models"
NOVI_SAD_MAP_DIR = NOVI_SAD_ARTIFACT_DIR / "maps"
NOVI_SAD_REPORT_DIR = NOVI_SAD_ARTIFACT_DIR / "reports"
NOVI_SAD_REFERENCE_MANIFEST = NOVI_SAD_ARTIFACT_DIR / "reference_manifest.json"
LEGACY_CACHE_DIR = CACHE_DIR / "legacy"
LEGACY_ARTIFACT_DIR = REPOSITORY_ROOT / "artifacts" / "legacy" / "runtime"
LEGACY_NET_CACHE = LEGACY_CACHE_DIR / "net0.pkl"
LEGACY_NET_OUTPUT = LEGACY_ARTIFACT_DIR / "ppnet.json"
LEGACY_SCENARIO_MAP = LEGACY_ARTIFACT_DIR / "scenario.html"
LEGACY_GDF_TEST_MAP = LEGACY_ARTIFACT_DIR / "mapgdftest.html"

ACTIVE_CONFIG = Path(
    os.environ.get("MVGRID_CONFIG", str(CONFIG_DIR / "novi_sad.json"))
).expanduser().resolve()
CACHE_SNAPSHOT = CACHE_DIR / "data.pkl"
OSM_SUBSTATION_CACHE = CACHE_DIR / "osm_substations_bbox.json"
OSM_SUBSTATION_REFERENCE = NOVI_SAD_INPUT_DIR / "osm_substations_bbox.json"


def ensure_runtime_directories() -> None:
    """Create only ignored runtime directories; reference directories are versioned."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def display_path(path: Path) -> str:
    """Return a portable repository-relative path when possible."""
    try:
        path = path.resolve().relative_to(REPOSITORY_ROOT)
    except ValueError:
        path = path.resolve()
    return path.as_posix()
