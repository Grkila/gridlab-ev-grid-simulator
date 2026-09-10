"""Generate, solve, map, and validate the unified Novi Sad planning model."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_input_manifest() -> None:
    snapshot = Path("data.pkl")
    config = Path("config.json")
    packages = {}
    for package in ("geopandas", "networkx", "osmnx", "pandapower", "shapely"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    manifest = {
        "scope": "traceability for the local cached OSM-derived input snapshot",
        "osm_snapshot": {
            "path": str(snapshot),
            "sha256": sha256(snapshot),
            "last_modified_utc": datetime.fromtimestamp(
                snapshot.stat().st_mtime, timezone.utc
            ).isoformat(),
        },
        "config": {"path": str(config), "sha256": sha256(config)},
        "package_versions": packages,
        "reproducibility_warning": (
            "data.pkl is local and gitignored; this manifest traces generated artifacts "
            "to that snapshot but does not make a fresh clone bit-for-bit reproducible."
        ),
    }
    Path("novi_sad_input_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-osm",
        action="store_true",
        help="rebuild the cached OSM polygon, land use, and street graph",
    )
    parser.add_argument(
        "--skip-map",
        action="store_true",
        help="skip generation of the interactive HTML map",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="skip the power-flow validation and uniform-demand stress test",
    )
    args = parser.parse_args()

    import stages
    import utils

    if args.refresh_osm:
        Path("data.pkl").unlink(missing_ok=True)
        Path("osm_substations_bbox.json").unlink(missing_ok=True)
    data = utils.data_un("data.pkl") or {"last_saved": 0}
    start = int(data.get("last_saved", 0)) + 1
    if start <= 3:
        stages.run_stages(data, stend=(start, 3))
    write_input_manifest()

    if args.skip_map:
        Path("novi_sad_simulation_map.html").unlink(missing_ok=True)
    if args.skip_validation:
        Path("novi_sad_validation_report.json").unlink(missing_ok=True)
        Path("novi_sad_validation_report.md").unlink(missing_ok=True)

    import generate_synthetic_transformers
    import generate_inferred_feeders
    import build_unified_novi_sad_model

    generate_synthetic_transformers.main()
    generate_inferred_feeders.main()
    build_unified_novi_sad_model.main()

    if not args.skip_map:
        import generate_novi_sad_map

        generate_novi_sad_map.main()
    if not args.skip_validation:
        import validate_novi_sad_model

        validate_novi_sad_model.main()


if __name__ == "__main__":
    main()
