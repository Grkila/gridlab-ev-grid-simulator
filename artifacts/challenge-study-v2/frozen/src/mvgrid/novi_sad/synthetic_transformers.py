"""Create a calibrated, clearly labelled synthetic MV/LV transformer inventory for Novi Sad."""
from __future__ import annotations

import csv
import json
import math
import random
from mvgrid.legacy import utils
from mvgrid.paths import NOVI_SAD_GENERATED_DIR


POINT_COUNT = 2648
ANNUAL_CONSUMPTION_MWH = 1_147_635.0
PEAK_TO_MEAN_RATIO = 1.64
MV_20KV_CAPACITY_MW = 299.0
SEED = 20250910
OUTPUT_CSV = NOVI_SAD_GENERATED_DIR / "novi_sad_synthetic_transformers.csv"
OUTPUT_SUMMARY = NOVI_SAD_GENERATED_DIR / "novi_sad_synthetic_transformers_summary.json"
LAND_USE_FACTORS = {
    "residential": 1.0,
    "industrial": 1.8,
    "military": 0.4,
    "commercial": 2.5,
    "retail": 2.2,
}


def point_in_geometry(geometry, rng):
    min_x, min_y, max_x, max_y = geometry.bounds
    for _ in range(10_000):
        point = geometry.representative_point() if min_x == max_x or min_y == max_y else None
        if point is None:
            from shapely.geometry import Point
            point = Point(rng.uniform(min_x, max_x), rng.uniform(min_y, max_y))
        if geometry.contains(point):
            return point
    return geometry.representative_point()


def allocate_counts(weights):
    raw = [POINT_COUNT * weight / sum(weights) for weight in weights]
    counts = [max(1, math.floor(value)) for value in raw]
    remainder = POINT_COUNT - sum(counts)
    order = sorted(range(len(raw)), key=lambda index: raw[index] - math.floor(raw[index]), reverse=True)
    for index in order[:remainder]:
        counts[index] += 1
    if remainder < 0:
        for index in reversed(order):
            while remainder < 0 and counts[index] > 1:
                counts[index] -= 1
                remainder += 1
    return counts


def main():
    data = utils.data_un("data.pkl")
    if data.get("last_saved", 0) < 2:
        raise RuntimeError("Run the Novi Sad reconstruction through stage 2 first.")

    city_polygon = data["poly"]
    land_use = data["lu"]
    zones = []
    for osmid, row in land_use.iterrows():
        clipped = row.geometry.intersection(city_polygon)
        if clipped.is_empty or clipped.area == 0:
            continue
        factor = LAND_USE_FACTORS.get(row["tag"], 1.0)
        weight = clipped.area * factor
        if weight > 0:
            zones.append({"osmid": osmid, "land_use": row["tag"], "geometry": clipped, "weight": weight})
    if not zones:
        raise RuntimeError("No usable land-use polygons were found.")

    counts = allocate_counts([zone["weight"] for zone in zones])
    total_weight = sum(zone["weight"] for zone in zones)
    rng = random.Random(SEED)
    rows = []
    for zone, count in zip(zones, counts):
        zone_annual_mwh = ANNUAL_CONSUMPTION_MWH * zone["weight"] / total_weight
        for _ in range(count):
            point = point_in_geometry(zone["geometry"], rng)
            rows.append({
                "synthetic_id": f"SYN-{len(rows) + 1:04d}",
                "parent_landuse_osm_id": zone["osmid"],
                "land_use": zone["land_use"],
                "longitude": round(point.x, 7),
                "latitude": round(point.y, 7),
                "annual_consumption_mwh": zone_annual_mwh / count,
            })
    # Preserve the supplied annual total exactly despite CSV-friendly floating-point values.
    rows[-1]["annual_consumption_mwh"] += ANNUAL_CONSUMPTION_MWH - sum(row["annual_consumption_mwh"] for row in rows)
    for row in rows:
        row["peak_demand_mw"] = row["annual_consumption_mwh"] / 8760 * PEAK_TO_MEAN_RATIO
        row["provenance"] = "synthetic land-use allocation; not a verified utility asset"

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    peak_mw = sum(row["peak_demand_mw"] for row in rows)
    summary = {
        "point_count": len(rows),
        "annual_consumption_mwh": ANNUAL_CONSUMPTION_MWH,
        "annual_average_mw": ANNUAL_CONSUMPTION_MWH / 8760,
        "peak_to_mean_ratio": PEAK_TO_MEAN_RATIO,
        "calibrated_peak_demand_mw": peak_mw,
        "mv_20kv_capacity_mw": MV_20KV_CAPACITY_MW,
        "capacity_headroom_mw": MV_20KV_CAPACITY_MW - peak_mw,
        "seed": SEED,
        "provenance": "Synthetic, land-use-weighted allocation calibrated to user-supplied 2025 consumption/capacity figures.",
    }
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Created {OUTPUT_CSV.resolve()} and {OUTPUT_SUMMARY.resolve()}")


if __name__ == "__main__":
    main()
