"""Create an interactive map of the unified Novi Sad planning model."""
from __future__ import annotations

import os as os_module
import csv
import json

import folium
from folium.plugins import MarkerCluster
from shapely.geometry import Point
from mvgrid.legacy import osm, utils
from mvgrid.paths import (
    NOVI_SAD_GENERATED_DIR,
    NOVI_SAD_MAP_DIR,
    OSM_SUBSTATION_CACHE,
    OSM_SUBSTATION_REFERENCE,
    ensure_runtime_directories,
)


OUTPUT = NOVI_SAD_MAP_DIR / "novi_sad_simulation_map.html"
SYNTHETIC_INVENTORY = NOVI_SAD_GENERATED_DIR / "novi_sad_synthetic_transformers.csv"
INFERRED_FEEDERS = NOVI_SAD_GENERATED_DIR / "novi_sad_inferred_feeders.geojson"
SEEDED_STATIONS = NOVI_SAD_GENERATED_DIR / "novi_sad_seeded_substations.json"
LEGACY_ROUTES = NOVI_SAD_GENERATED_DIR / "novi_sad_legacy_35kv_routes.geojson"


def get_all_osm_substations(poly):
    refresh = os_module.environ.get("MVGRID_REFRESH_OSM") == "1"
    source = OSM_SUBSTATION_CACHE
    if not source.exists() and not refresh:
        source = OSM_SUBSTATION_REFERENCE
    if source.exists():
        cached = json.loads(source.read_text(encoding="utf-8"))
        return [
            element for element in cached
            if poly.covers(Point(element_location(element)[1], element_location(element)[0]))
        ]
    polygon = " ".join(f"{lat} {lon}" for lon, lat in poly.exterior.coords)
    query = f'[out:json][timeout:90];nwr["power"="substation"](poly:"{polygon}");out center tags;'
    elements = osm.op_query_json(query)["elements"]
    ensure_runtime_directories()
    temporary = OSM_SUBSTATION_CACHE.with_suffix(".tmp")
    temporary.write_text(json.dumps(elements, separators=(",", ":")), encoding="utf-8")
    temporary.replace(OSM_SUBSTATION_CACHE)
    return elements


def element_location(element):
    if element["type"] == "node":
        return element["lat"], element["lon"]
    center = element.get("center")
    return center["lat"], center["lon"]


def main() -> None:
    data = utils.data_un("data.pkl")
    if data.get("last_saved", 0) < 3:
        raise RuntimeError("Run run_novi_sad.py first to generate the OSM study data.")

    poly = data["poly"]
    center = [poly.centroid.y, poly.centroid.x]
    grid_map = folium.Map(location=center, zoom_start=12, tiles="OpenStreetMap", control_scale=True)

    folium.GeoJson(
        poly,
        name="Novi Sad study area",
        style_function=lambda _: {"color": "#555555", "weight": 2, "fillOpacity": 0},
    ).add_to(grid_map)

    inferred_edge_count = 0
    if INFERRED_FEEDERS.exists():
        feeder_data = json.loads(INFERRED_FEEDERS.read_text(encoding="utf-8"))
        inferred_edge_count = len(feeder_data["features"])
        inferred_layer = folium.FeatureGroup(
            name=f"Inferred feeders to synthetic points ({inferred_edge_count:,} segments)",
            show=True,
        )
        folium.GeoJson(
            feeder_data,
            style_function=lambda feature: {
                "color": "#7b3294" if feature["properties"].get("kind") == "feeder_segment" else "#cc5500",
                "weight": 1.4 if feature["properties"].get("kind") == "feeder_segment" else 2.5,
                "opacity": 0.55 if feature["properties"].get("kind") == "feeder_segment" else 0.8,
                "dashArray": None if feature["properties"].get("kind") == "feeder_segment" else "6 7",
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["source_name", "allocated_peak_mw"],
                aliases=["Assigned source", "Downstream synthetic peak (MW)"],
                localize=True,
                sticky=False,
            ),
            popup=folium.GeoJsonPopup(
                fields=["source_name", "length_m", "provenance"],
                aliases=["Assigned source", "Segment length (m)", "Status"],
                localize=True,
            ),
        ).add_to(inferred_layer)
        inferred_layer.add_to(grid_map)

    primary_count = 0
    secondary_count = 0
    simulated_primary_ids = set()
    simulated_delivery_ids = set()
    if SEEDED_STATIONS.exists():
        station_data = json.loads(SEEDED_STATIONS.read_text(encoding="utf-8"))
        primary_count = len(station_data["primary_stations"])
        simulated_primary_ids = {
            int(station["osm_id"])
            for station in station_data["primary_stations"]
            if station.get("osm_id") is not None
        }
        verified_primary_layer = folium.FeatureGroup(name="EDS primary stations — name-verified OSM positions (3)", show=True)
        inferred_primary_layer = folium.FeatureGroup(name="EDS primary stations — inferred OSM positions (6)", show=True)
        for station in station_data["primary_stations"]:
            direct = station["direct_20kv"]
            location_status = station["coordinate_status"]
            coordinate_verified = location_status.startswith("verified")
            if station.get("sections"):
                section_lines = []
                for section in station["sections"]:
                    utilization = section.get("utilization_pct")
                    utilization_text = (
                        f"{utilization:.1f}%" if utilization is not None else "not reported"
                    )
                    section_lines.append(
                        f"{section['ratio']}: {section['installed_mva']:.1f} MVA, "
                        f"Pmax {section['baseline_pmax_mw']:.1f} MW, "
                        f"utilization {utilization_text}"
                    )
                section_html = "<br>".join(section_lines)
            else:
                section_html = (
                    f"{station['ratio']}: {station['installed_mva']:.1f} MVA, "
                    f"Pmax {station['baseline_pmax_mw']:.1f} MW, "
                    f"utilization {station['utilization_pct']:.1f}%"
                )
            folium.Marker(
                location=(station["lat"], station["lon"]),
                tooltip=f"{station['name']} — {station['ratio']}",
                popup=folium.Popup(
                    f"<b>{station['name']}</b><br>Voltage: {station['ratio']}<br>"
                    f"2024 EDS sections:<br>{section_html}<br>"
                    f"Coordinate: {location_status}",
                    max_width=340,
                ),
                icon=folium.Icon(
                    color="red" if coordinate_verified else ("orange" if direct else "darkpurple"),
                    icon="flash" if direct else "transfer",
                    prefix="glyphicon",
                ),
            ).add_to(verified_primary_layer if coordinate_verified else inferred_primary_layer)
        verified_primary_layer.add_to(grid_map)
        inferred_primary_layer.add_to(grid_map)

        secondary_count = len(station_data["legacy_secondary_stations"])
        simulated_delivery_ids = {
            int(station["osm_id"])
            for station in station_data["legacy_secondary_stations"]
            if station.get("osm_id") is not None
        }
        legacy_station_layer = folium.FeatureGroup(name="Legacy 35/10 kV stations (6, inferred positions)", show=True)
        for station in station_data["legacy_secondary_stations"]:
            folium.CircleMarker(
                location=(station["lat"], station["lon"]),
                radius=6,
                color="#008c95",
                fill=True,
                fill_opacity=0.9,
                tooltip=f"{station['name']} — {station['ratio']}",
                popup=folium.Popup(
                    f"<b>{station['name']}</b><br>{station['ratio']}<br>"
                    f"EDS-listed station; coordinate is an inferred match to an unnamed OSM feature.<br>"
                    f"Installed reference: {station['installed_mva']:.1f} MVA",
                    max_width=330,
                ),
            ).add_to(legacy_station_layer)
        legacy_station_layer.add_to(grid_map)

    if LEGACY_ROUTES.exists():
        legacy_data = json.loads(LEGACY_ROUTES.read_text(encoding="utf-8"))
        legacy_layer = folium.FeatureGroup(name="Inferred legacy 35 kV paths", show=True)
        folium.GeoJson(
            legacy_data,
            style_function=lambda _: {"color": "#008c95", "weight": 3, "opacity": 0.75, "dashArray": "8 6"},
            tooltip=folium.GeoJsonTooltip(
                fields=["upstream", "secondary", "route_length_km"],
                aliases=["110/35 source", "35/10 station", "Inferred route (km)"],
                localize=True,
            ),
            popup=folium.GeoJsonPopup(fields=["provenance"], aliases=["Status"]),
        ).add_to(legacy_layer)
        legacy_layer.add_to(grid_map)

    all_stations = get_all_osm_substations(poly)
    all_stations_layer = folium.FeatureGroup(name="All OSM-mapped substations", show=True)
    for station in all_stations:
        osmid = station["id"]
        tags = station.get("tags", {})
        lat, lon = element_location(station)
        kind = tags.get("substation", "unspecified")
        voltage = tags.get("voltage", "not mapped")
        is_primary_source = osmid in simulated_primary_ids
        is_delivery_station = osmid in simulated_delivery_ids
        is_modelled = is_primary_source or is_delivery_station
        color = (
            "red" if is_primary_source
            else "#008c95" if is_delivery_station
            else "orange" if kind == "distribution"
            else "gray"
        )
        model_status = (
            "Included as a simulated primary source"
            if is_primary_source
            else "Included as a simulated 35/10 kV delivery station"
            if is_delivery_station
            else "Mapped for reference only"
        )
        name = tags.get("name:sr-Latn") or tags.get("name:en") or tags.get("name") or "Unnamed OSM substation"
        folium.CircleMarker(
            location=(lat, lon),
            radius=6 if is_modelled else 4,
            color=color,
            fill=True,
            fill_opacity=0.75,
            tooltip=f"{name} — {kind}",
            popup=folium.Popup(
                f"<b>{name}</b><br>OSM {station['type']} {osmid}<br>"
                f"Type: {kind}<br>Voltage: {voltage}<br>"
                f"{model_status}",
                max_width=280,
            ),
        ).add_to(all_stations_layer)
    all_stations_layer.add_to(grid_map)

    if SYNTHETIC_INVENTORY.exists():
        synthetic_layer = folium.FeatureGroup(name="Synthetic MV/LV service points (2,648)", show=True)
        cluster = MarkerCluster(name="Synthetic transformer clusters").add_to(synthetic_layer)
        with SYNTHETIC_INVENTORY.open(encoding="utf-8", newline="") as file:
            for point in csv.DictReader(file):
                folium.CircleMarker(
                    location=(float(point["latitude"]), float(point["longitude"])),
                    radius=3,
                    color="#7b3294",
                    fill=True,
                    fill_opacity=0.65,
                    tooltip=f"{point['synthetic_id']} — synthetic {point['land_use']} service point",
                    popup=folium.Popup(
                        f"<b>{point['synthetic_id']}</b><br>Synthetic service point; not a verified transformer.<br>"
                        f"Land use: {point['land_use']}<br>Annual allocation: {float(point['annual_consumption_mwh']):.1f} MWh<br>"
                        f"Peak allocation: {float(point['peak_demand_mw']):.3f} MW",
                        max_width=280,
                    ),
                ).add_to(cluster)
        synthetic_layer.add_to(grid_map)

    legend = f'''<div style="position: fixed; bottom: 25px; left: 25px; z-index: 1000;
        background: white; border: 1px solid #777; padding: 8px; font-size: 13px;">
        <b>Novi Sad power infrastructure</b><br>
        {len(all_stations)} OSM-mapped substations; {primary_count} EDS primary seeds; {secondary_count} legacy secondary seeds<br>
        <span style="color:#d73027">⚡</span> direct 110/20 kV, name-verified OSM position (3)<br>
        <span style="color:#ff7f00">⚡</span> direct 110/20 kV, inferred OSM position (4)<br>
        <span style="color:#5b2c83">⚡</span> 110/35 kV legacy source, inferred OSM position (2)<br>
        <span style="color:#008c95">●</span> EDS-listed 35/10 kV station, inferred position/path<br>
        <span style="color:#ff7f00">●</span> distribution substation<br>
        <span style="color:#777">●</span> other or unspecified OSM substation
        <br><span style="color:#7b3294">●</span> synthetic land-use service point
        <br><span style="color:#7b3294">━</span> capacity-balanced inferred feeder ({inferred_edge_count:,} features)
        <br><small>Purple assets are planning proxies, not verified utility records.</small>
        </div>'''
    grid_map.get_root().html.add_child(folium.Element(legend))

    folium.LayerControl(collapsed=False).add_to(grid_map)
    grid_map.save(OUTPUT)
    print(f"Created {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
