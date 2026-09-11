"""Generate, solve, map, and validate the unified Novi Sad planning model."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
import os
from pathlib import Path

from mvgrid.paths import (
    ACTIVE_CONFIG,
    CACHE_SNAPSHOT,
    NOVI_SAD_ARTIFACT_DIR,
    NOVI_SAD_GENERATED_DIR,
    NOVI_SAD_INPUT_DIR,
    NOVI_SAD_MAP_DIR,
    NOVI_SAD_MODEL_DIR,
    NOVI_SAD_REFERENCE_MANIFEST,
    NOVI_SAD_REPORT_DIR,
    OSM_SUBSTATION_CACHE,
    display_path,
    ensure_runtime_directories,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_text_digest(path: Path) -> tuple[int, str]:
    """Hash generated text with LF endings so verification is OS-independent."""
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return len(content), hashlib.sha256(content).hexdigest()


def write_input_manifest(refresh_requested_utc: str | None = None) -> None:
    snapshot = CACHE_SNAPSHOT
    config = ACTIVE_CONFIG
    packages = {}
    for package in ("geopandas", "networkx", "osmnx", "pandapower", "shapely"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    manifest = {
        "scope": "traceability for the local cached OSM-derived input snapshot",
        "osm_snapshot": {
            "path": display_path(snapshot),
            "sha256": sha256(snapshot),
            "cache_file_modified_utc": datetime.fromtimestamp(
                snapshot.stat().st_mtime, timezone.utc
            ).isoformat(),
            "acquisition_time_status": (
                "refresh request time recorded; individual legacy OSM query times are not retained"
                if refresh_requested_utc
                else "unknown; legacy cache does not retain authoritative OSM acquisition time"
            ),
            "refresh_requested_utc": refresh_requested_utc,
            "source_services": ["Nominatim", "Overpass API", "OpenStreetMap"],
        },
        "config": {
            "path": display_path(config),
            "sha256": sha256(config),
        },
        "package_versions": packages,
        "reproducibility_warning": (
            "data.pkl is local and gitignored; this manifest traces generated artifacts "
            "to that snapshot but does not make a fresh clone bit-for-bit reproducible."
        ),
    }
    (NOVI_SAD_GENERATED_DIR / "novi_sad_input_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def write_reference_manifest() -> None:
    """Bind the complete checked reference bundle to exact bytes."""
    roots = (
        NOVI_SAD_INPUT_DIR,
        NOVI_SAD_GENERATED_DIR,
        NOVI_SAD_MODEL_DIR,
        NOVI_SAD_MAP_DIR,
        NOVI_SAD_REPORT_DIR,
    )
    files = sorted(path for root in roots for path in root.rglob("*") if path.is_file())
    entries = []
    for path in files:
        canonical_size, digest = canonical_text_digest(path)
        entries.append(
            {
                "path": display_path(path),
                "canonical_size_bytes": canonical_size,
                "sha256_lf_normalized": digest,
            }
        )
    payload = {
        "schema_version": 1,
        "scope": "single complete Novi Sad challenge reference bundle; text normalized to LF",
        "files": entries,
    }
    NOVI_SAD_REFERENCE_MANIFEST.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
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
        help="leave the existing interactive HTML map unchanged",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="leave existing validation reports unchanged",
    )
    args = parser.parse_args()

    ensure_runtime_directories()

    refresh_requested_utc = None
    if args.refresh_osm:
        refresh_requested_utc = datetime.now(timezone.utc).isoformat()
        CACHE_SNAPSHOT.unlink(missing_ok=True)
        OSM_SUBSTATION_CACHE.unlink(missing_ok=True)
        os.environ["MVGRID_REFRESH_OSM"] = "1"
    elif not CACHE_SNAPSHOT.exists():
        parser.error(
            "trusted cache data/cache/data.pkl is missing; use --refresh-osm "
            "to explicitly download current OSM data"
        )
    from mvgrid.legacy import stages, utils

    data = utils.data_un("data.pkl") or {"last_saved": 0}
    if not args.refresh_osm and int(data.get("last_saved", 0)) < 3:
        parser.error(
            "the local stage cache is incomplete; use --refresh-osm to rebuild it"
        )
    start = int(data.get("last_saved", 0)) + 1
    if start <= 3:
        stages.run_stages(data, stend=(start, 3))
    write_input_manifest(refresh_requested_utc)

    from . import synthetic_transformers, inferred_feeders, model

    synthetic_transformers.main()
    inferred_feeders.main()
    model.main()

    if not args.skip_map:
        from . import map as map_module

        map_module.main()
    if not args.skip_validation:
        from . import validation

        validation.main()
    if not args.skip_map and not args.skip_validation:
        write_reference_manifest()


if __name__ == "__main__":
    main()
