"""Infer a transparent street-routed feeder forest for the synthetic Novi Sad inventory.

The output is a planning proxy, not an as-built utility network.  Each synthetic
MV/LV service point is snapped to the OSM street graph and connected to one of
seven EDS-listed stations with direct 110/20 kV function. Shared street edges
form a capacity-balanced radial shortest-path forest.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import networkx as nx
from scipy.spatial import cKDTree
from shapely.geometry import LineString, mapping

import utils


INVENTORY = Path("novi_sad_synthetic_transformers.csv")
ASSIGNMENTS = Path("novi_sad_synthetic_feeder_assignments.csv")
OUTPUT_GEOJSON = Path("novi_sad_inferred_feeders.geojson")
OUTPUT_SUMMARY = Path("novi_sad_inferred_feeders_summary.json")
OUTPUT_STATIONS = Path("novi_sad_seeded_substations.json")
OUTPUT_LEGACY = Path("novi_sad_legacy_35kv_routes.geojson")
ROUTING_TARGET_LOADING = 0.86
ROUTING_POWER_FACTOR = 0.97
ALLOCATION_BALANCE_DISTANCE_KM = 5.0

# Equipment, 2024 Pmax, and utilization come from EDS's public 2025-2034
# development plan (base year 2024).  Only three coordinates are named in OSM;
# the remaining coordinates are explicitly recorded as locality-matched inferences.
PRIMARY_STATIONS = [
    {"id": "NS1", "name": "Novi Sad 1 - Ledinci", "ratio": "110/20 + 110/35", "direct_20kv": True,
     "installed_mva": 63.0, "direct_20kv_mva": 31.5,
     "baseline_pmax_mw": 7.5, "utilization_pct": 24.2,
     "derived_total_pmax_mw": 23.0, "max_section_utilization_pct": 50.1,
     "sections": [
         {"ratio": "110/20", "installed_mva": 31.5, "baseline_pmax_mw": 7.5, "utilization_pct": 24.2},
         {"ratio": "110/35", "installed_mva": 31.5, "baseline_pmax_mw": 15.5, "utilization_pct": 50.1},
     ],
     "lat": 45.2172125, "lon": 19.8157080, "osm_id": 356832545, "coordinate_status": "inferred match to unnamed OSM substation in Ledinci"},
    {"id": "NS2", "name": "Novi Sad 2", "ratio": "110/35", "direct_20kv": False,
     "installed_mva": 51.5, "baseline_pmax_mw": 30.0, "utilization_pct": 58.3,
     "lat": 45.2727450, "lon": 19.8461553, "osm_id": 142883147, "coordinate_status": "inferred match to unnamed OSM distribution substation"},
    {"id": "NS4", "name": "Novi Sad 4 - Sever III", "ratio": "110/35", "direct_20kv": False,
     "installed_mva": 126.0, "baseline_pmax_mw": 54.4, "utilization_pct": 43.4,
     "lat": 45.2774527, "lon": 19.7990241, "osm_id": 141886238, "coordinate_status": "inferred match to unnamed OSM distribution substation in Sever III"},
    {"id": "NS5", "name": "Novi Sad 5 - Detelinara", "ratio": "110/20/10", "direct_20kv": True,
     "installed_mva": 63.0, "baseline_pmax_mw": 56.9, "utilization_pct": 91.0,
     "lat": 45.2604530, "lon": 19.8048469, "osm_id": 365786756, "coordinate_status": "verified by named OSM feature"},
    {"id": "NS6", "name": "Novi Sad 6 - Miseluk", "ratio": "110/20", "direct_20kv": True,
     "installed_mva": 63.0, "baseline_pmax_mw": 28.0, "utilization_pct": 44.5,
     "lat": 45.2269229, "lon": 19.8735339, "osm_id": 1431014564, "coordinate_status": "inferred match to unnamed OSM substation in Miseluk"},
    {"id": "NS7", "name": "Novi Sad 7 - Juzni Telep", "ratio": "110/20 + 110/35", "direct_20kv": True,
     "installed_mva": 83.0, "direct_20kv_mva": 63.0, "baseline_pmax_mw": 59.8, "utilization_pct": 95.4,
     "sections": [
         {"ratio": "110/20", "installed_mva": 63.0, "baseline_pmax_mw": 59.8, "utilization_pct": 95.4},
         {"ratio": "110/35", "installed_mva": 20.0, "baseline_pmax_mw": 0.0, "utilization_pct": None},
     ],
     "lat": 45.2315098, "lon": 19.8139568, "osm_id": 220232167, "coordinate_status": "verified by named OSM feature"},
    {"id": "NS9", "name": "Novi Sad 9 - Rafinerija", "ratio": "110/20/10", "direct_20kv": True,
     "installed_mva": 63.0, "baseline_pmax_mw": 26.7, "utilization_pct": 42.4,
     "lat": 45.2806465, "lon": 19.8789331, "osm_id": 359523533, "coordinate_status": "inferred match to unnamed OSM distribution substation in refinery area"},
    {"id": "RIM", "name": "Rimski Sancevi", "ratio": "110/20", "direct_20kv": True,
     "installed_mva": 63.0, "baseline_pmax_mw": 31.7, "utilization_pct": 51.1,
     "lat": 45.3101654, "lon": 19.8272059, "osm_id": 365927134, "coordinate_status": "verified by named OSM feature"},
    {"id": "FUT", "name": "Futog", "ratio": "110/20", "direct_20kv": True,
     "installed_mva": 63.0, "baseline_pmax_mw": 33.2, "utilization_pct": 54.3,
     "lat": 45.2601681, "lon": 19.7008355, "osm_id": 367560187, "coordinate_status": "inferred match to unnamed OSM substation east of Futog-Planta-Kisac road"},
]

LEGACY_SECONDARY_STATIONS = [
    {"id": "LIMAN", "name": "Liman", "ratio": "35/10 (plus 35/20 section)", "installed_mva": 32.0, "lat": 45.2440300, "lon": 19.8403917, "osm_id": 219386583},
    {"id": "CENTAR", "name": "Centar", "ratio": "35/10", "installed_mva": 32.0, "lat": 45.2451338, "lon": 19.8484361, "osm_id": 222835326},
    {"id": "PODBARA", "name": "Podbara", "ratio": "35/10", "installed_mva": 32.0, "lat": 45.2616944, "lon": 19.8453786, "osm_id": 13476783676},
    {"id": "SEVER", "name": "Sever", "ratio": "35/10", "installed_mva": 16.0, "lat": 45.2760796, "lon": 19.8223915, "osm_id": 1539728495},
    {"id": "IND", "name": "Industrijska", "ratio": "35/10 (plus 35/20 section)", "installed_mva": 32.0, "lat": 45.2688048, "lon": 19.8308089, "osm_id": 1346366291},
    {"id": "TELEP", "name": "Telep", "ratio": "35/10", "installed_mva": 16.0, "lat": 45.2517402, "lon": 19.7920114, "osm_id": 197685483},
]

# These two upstream relationships are explicitly documented in the EDS plan.
# The remaining legacy-source associations are planning inferences chosen by
# minimum road-network distance and are labelled as such in the output.
DOCUMENTED_LEGACY_UPSTREAM = {"CENTAR": "NS2", "LIMAN": "NS4"}


def edge_record(graph, u, v):
    choices = graph.get_edge_data(u, v)
    return min(choices.values(), key=lambda item: float(item.get("length", 0.0)))


def edge_geometry(graph, u, v, record):
    geometry = record.get("geometry")
    if geometry is not None:
        return geometry
    return LineString(
        [
            (graph.nodes[u]["x"], graph.nodes[u]["y"]),
            (graph.nodes[v]["x"], graph.nodes[v]["y"]),
        ]
    )


def nearest_nodes(graph, coordinates):
    """Return nearest graph node IDs using a local lon/lat KD-tree."""
    node_ids = list(graph.nodes)
    tree = cKDTree([(graph.nodes[node]["x"], graph.nodes[node]["y"]) for node in node_ids])
    _, positions = tree.query(coordinates)
    return [node_ids[int(position)] for position in positions]


def road_routing_graph(graph):
    """Keep a connected road-like graph and exclude implausible cable proxies."""
    forbidden = {"steps", "path", "footway", "cycleway", "pedestrian"}
    clean = graph.copy()
    remove = []
    for u, v, key, record in clean.edges(keys=True, data=True):
        highway = record.get("highway", "")
        highway_values = set(highway if isinstance(highway, list) else [highway])
        route = record.get("route", "")
        if route == "ferry" or highway_values & forbidden:
            remove.append((u, v, key))
    clean.remove_edges_from(remove)
    clean.remove_nodes_from(list(nx.isolates(clean)))
    largest = max(nx.connected_components(clean), key=len)
    return clean.subgraph(largest).copy()


def legacy_connections(graph):
    """Resolve documented and inferred NS2/NS4-to-secondary associations."""
    primaries = [station for station in PRIMARY_STATIONS if not station["direct_20kv"]]
    primary_nodes = nearest_nodes(graph, [(row["lon"], row["lat"]) for row in primaries])
    secondary_nodes = nearest_nodes(
        graph, [(row["lon"], row["lat"]) for row in LEGACY_SECONDARY_STATIONS]
    )
    connections = []
    for secondary, target_node in zip(LEGACY_SECONDARY_STATIONS, secondary_nodes):
        documented_id = DOCUMENTED_LEGACY_UPSTREAM.get(secondary["id"])
        candidates = []
        for primary, source_node in zip(primaries, primary_nodes):
            if documented_id is not None and primary["id"] != documented_id:
                continue
            length, path = nx.single_source_dijkstra(
                graph, source_node, target=target_node, weight="length"
            )
            candidates.append((length, path, primary, source_node))
        length, path, primary, source_node = min(candidates, key=lambda item: item[0])
        connections.append(
            {
                "secondary": secondary,
                "secondary_node": int(target_node),
                "primary": primary,
                "primary_node": int(source_node),
                "length_m": float(length),
                "path": path,
                "association_status": (
                    "documented in EDS plan"
                    if documented_id
                    else "inferred by minimum road-network distance"
                ),
            }
        )
    return connections


def main() -> None:
    if not INVENTORY.exists():
        raise RuntimeError("Run generate_synthetic_transformers.py first.")

    data = utils.data_un("data.pkl")
    graph = road_routing_graph(data["G"].to_undirected())
    direct_sources = [station for station in PRIMARY_STATIONS if station["direct_20kv"]]
    resolved_legacy = legacy_connections(graph)
    source_rows = []
    source_items = [
        {
            **station,
            "primary_station_id": station["id"],
            "primary_station_name": station["name"],
            "delivery_voltage_kv": 20.0,
            "delivery_kind": "direct_110_20",
            "routing_capacity_mva": station.get("direct_20kv_mva", station["installed_mva"]),
        }
        for station in direct_sources
    ] + [
        {
            **connection["secondary"],
            "primary_station_id": connection["primary"]["id"],
            "primary_station_name": connection["primary"]["name"],
            "delivery_voltage_kv": 10.0,
            "delivery_kind": "legacy_35_10",
            "routing_capacity_mva": connection["secondary"]["installed_mva"],
            "baseline_pmax_mw": 0.0,
        }
        for connection in resolved_legacy
    ]
    source_nodes = nearest_nodes(
        graph,
        [(row["lon"], row["lat"]) for row in source_items],
    )
    for row, node in zip(source_items, source_nodes):
        source_rows.append(
            {
                "osmid": int(row["osm_id"]),
                "station_id": row["id"],
                "name": row["name"],
                "node": int(node),
                "installed_mva": row["installed_mva"],
                "routing_capacity_mva": row["routing_capacity_mva"],
                "baseline_pmax_mw": row["baseline_pmax_mw"],
                "primary_station_id": row["primary_station_id"],
                "primary_station_name": row["primary_station_name"],
                "delivery_voltage_kv": row["delivery_voltage_kv"],
                "delivery_kind": row["delivery_kind"],
                "lat": row["lat"],
                "lon": row["lon"],
            }
        )
    source_by_node = {row["node"]: row for row in source_rows}

    with INVENTORY.open(encoding="utf-8", newline="") as file:
        points = list(csv.DictReader(file))
    target_nodes = nearest_nodes(
        graph,
        [(float(row["longitude"]), float(row["latitude"])) for row in points],
    )

    # Assign by road proximity while respecting both delivery-transformer and
    # upstream-primary limits. MW limits include power factor and a 90% planning
    # loading margin; NS2/NS4 are therefore constrained across all descendants.
    source_distances = {
        node: nx.single_source_dijkstra_path_length(graph, node, weight="length")
        for node in source_by_node
    }
    point_info = []
    assigned_peak = defaultdict(float)
    assigned_primary_peak = defaultdict(float)
    capacity_limit = {
        node: source_by_node[node]["routing_capacity_mva"]
        * ROUTING_TARGET_LOADING * ROUTING_POWER_FACTOR
        for node in source_by_node
    }
    delivery_capacity_by_primary = defaultdict(float)
    for source in source_rows:
        delivery_capacity_by_primary[source["primary_station_id"]] += source["routing_capacity_mva"]
    primary_capacity_limit = {}
    for station in PRIMARY_STATIONS:
        primary_rating = station.get("direct_20kv_mva", station["installed_mva"])
        effective_rating = min(primary_rating, delivery_capacity_by_primary[station["id"]])
        primary_capacity_limit[station["id"]] = (
            effective_rating * ROUTING_TARGET_LOADING * ROUTING_POWER_FACTOR
        )
    total_peak_mw = sum(float(point["peak_demand_mw"]) for point in points)
    baseline_total = sum(float(station["baseline_pmax_mw"]) for station in PRIMARY_STATIONS)
    primary_target = {
        station["id"]: total_peak_mw * float(station["baseline_pmax_mw"]) / baseline_total
        for station in PRIMARY_STATIONS
    }
    delivery_target = {}
    for source in source_rows:
        siblings = [
            item for item in source_rows
            if item["primary_station_id"] == source["primary_station_id"]
        ]
        sibling_capacity = sum(item["routing_capacity_mva"] for item in siblings)
        delivery_target[source["node"]] = (
            primary_target[source["primary_station_id"]]
            * source["routing_capacity_mva"] / sibling_capacity
        )
    point_order = sorted(
        enumerate(zip(points, target_nodes)),
        key=lambda item: float(item[1][0]["peak_demand_mw"]),
        reverse=True,
    )
    assigned_by_index = {}
    for index, (point, target_node) in point_order:
        target_node = int(target_node)
        peak_mw = float(point["peak_demand_mw"])
        feasible = [
            node for node, source in source_by_node.items()
            if assigned_peak[node] + peak_mw <= capacity_limit[node] + 1e-9
            and assigned_primary_peak[source["primary_station_id"]] + peak_mw
            <= primary_capacity_limit[source["primary_station_id"]] + 1e-9
        ]
        if not feasible:
            raise RuntimeError("Unable to allocate synthetic demand within nested station limits.")
        def allocation_score(node):
            source = source_by_node[node]
            distance_km = source_distances[node][target_node] / 1000.0
            delivery_fill = assigned_peak[node] / max(delivery_target[node], 1e-9)
            primary_fill = assigned_primary_peak[source["primary_station_id"]] / max(
                primary_target[source["primary_station_id"]], 1e-9
            )
            return distance_km + ALLOCATION_BALANCE_DISTANCE_KM * (delivery_fill + primary_fill)

        source_node = min(feasible, key=allocation_score)
        assigned_by_index[index] = {
            "index": index, "point": point, "target_node": target_node,
            "source_node": source_node, "peak_mw": peak_mw,
        }
        assigned_peak[source_node] += peak_mw
        assigned_primary_peak[source_by_node[source_node]["primary_station_id"]] += peak_mw
    point_info = [assigned_by_index[index] for index in range(len(points))]

    edge_peak_mw = defaultdict(float)
    edge_sources = {}
    assignments = []
    source_point_counts = defaultdict(int)
    source_peak_mw = defaultdict(float)

    for source_node, source in source_by_node.items():
        _, paths = nx.single_source_dijkstra(graph, source_node, weight="length")
        for info in point_info:
            if info["source_node"] != source_node:
                continue
            point = info["point"]
            target_node = info["target_node"]
            peak_mw = info["peak_mw"]
            path = paths[target_node]
            source_point_counts[source["osmid"]] += 1
            source_peak_mw[source["osmid"]] += peak_mw
            for u, v in zip(path, path[1:]):
                key = (source["osmid"], *tuple(sorted((int(u), int(v)))))
                edge_peak_mw[key] += peak_mw
                edge_sources[key] = source["osmid"]
            assignments.append(
                {
                    "synthetic_id": point["synthetic_id"],
                    "source_osm_id": source["osmid"],
                    "source_name": source["name"],
                    "delivery_station_id": source["station_id"],
                    "primary_station_id": source["primary_station_id"],
                    "primary_station_name": source["primary_station_name"],
                    "delivery_voltage_kv": source["delivery_voltage_kv"],
                    "street_graph_node": target_node,
                    "route_distance_km": source_distances[source_node][target_node] / 1000.0,
                    "peak_demand_mw": peak_mw,
                    "provenance": "capacity-balanced inferred shortest-path assignment on OSM streets; not an as-built feeder",
                }
            )

    with ASSIGNMENTS.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=assignments[0].keys())
        writer.writeheader()
        writer.writerows(assignments)

    features = []
    total_length_m = 0.0
    source_lengths = defaultdict(float)
    source_edge_counts = defaultdict(int)
    physical_edges = set()
    for (source_key, u, v), peak_mw in edge_peak_mw.items():
        physical_edges.add((u, v))
        record = edge_record(graph, u, v)
        length_m = float(record.get("length", 0.0))
        source_id = edge_sources[(source_key, u, v)]
        total_length_m += length_m
        source_lengths[source_id] += length_m
        source_edge_counts[source_id] += 1
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "feeder_segment",
                    "source_osm_id": source_id,
                    "source_name": next(row["name"] for row in source_rows if row["osmid"] == source_id),
                    "delivery_station_id": next(row["station_id"] for row in source_rows if row["osmid"] == source_id),
                    "primary_station_id": next(row["primary_station_id"] for row in source_rows if row["osmid"] == source_id),
                    "delivery_voltage_kv": next(row["delivery_voltage_kv"] for row in source_rows if row["osmid"] == source_id),
                    "road_node_u": u,
                    "road_node_v": v,
                    "allocated_peak_mw": peak_mw,
                    "length_m": length_m,
                    "provenance": "synthetic street-routed feeder segment; not verified utility geometry",
                },
                "geometry": mapping(edge_geometry(graph, u, v, record)),
            }
        )

    # Preserve an explicit visual connection for seeds that sit just outside
    # the original urban street-graph footprint (most notably Futog).
    for source in source_rows:
        node = graph.nodes[source["node"]]
        connector = LineString([(source["lon"], source["lat"]), (node["x"], node["y"])])
        if connector.length <= 1e-7:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "kind": "source_connector",
                "source_osm_id": source["osmid"],
                "source_name": source["name"],
                "allocated_peak_mw": source_peak_mw[source["osmid"]],
                "length_m": connector.length * 85_000,
                "provenance": "dotted inferred connector from seeded station to edge of available OSM street graph; route unverified",
            },
            "geometry": mapping(connector),
        })

    OUTPUT_GEOJSON.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")),
        encoding="utf-8",
    )

    # Route the legacy 35 kV path from NS2/NS4 to the central 35/10 kV stations.
    legacy_features = []
    for connection in resolved_legacy:
        secondary = connection["secondary"]
        primary = connection["primary"]
        length = connection["length_m"]
        path = connection["path"]
        association_status = connection["association_status"]
        coordinates = []
        for u, v in zip(path, path[1:]):
            record = edge_record(graph, u, v)
            geometry = edge_geometry(graph, u, v, record)
            coordinates.append(list(geometry.coords))
        legacy_features.append({
            "type": "Feature",
            "properties": {
                "upstream": primary["name"],
                "secondary": secondary["name"],
                "ratio": secondary["ratio"],
                "route_length_km": length / 1000.0,
                "upstream_association_status": association_status,
                "provenance": (
                    f"Upstream association {association_status}; street-routed 35 kV corridor is inferred and exact route is unverified"
                ),
            },
            "geometry": {"type": "MultiLineString", "coordinates": coordinates},
        })
    OUTPUT_LEGACY.write_text(
        json.dumps({"type": "FeatureCollection", "features": legacy_features}, separators=(",", ":")),
        encoding="utf-8",
    )

    station_output = {
        "source": "EDS Plan razvoja distributivnog sistema 2025-2034, base year 2024",
        "coordinate_warning": "Only NS5, NS7 and Rimski Sancevi are name-verified in OSM; every other identity-to-coordinate match is inferred and must not be treated as an as-built location.",
        "primary_stations": PRIMARY_STATIONS,
        "legacy_secondary_stations": [
            {**station, "coordinate_status": "inferred match to unnamed OSM substation near the EDS-listed locality"}
            for station in LEGACY_SECONDARY_STATIONS
        ],
    }
    OUTPUT_STATIONS.write_text(json.dumps(station_output, indent=2), encoding="utf-8")
    source_summary = []
    for source in source_rows:
        source_id = source["osmid"]
        source_summary.append(
            {
                "source_osm_id": source_id,
                "source_name": source["name"],
                "delivery_station_id": source["station_id"],
                "primary_station_id": source["primary_station_id"],
                "primary_station_name": source["primary_station_name"],
                "delivery_voltage_kv": source["delivery_voltage_kv"],
                "delivery_kind": source["delivery_kind"],
                "street_graph_root_node": source["node"],
                "installed_mva": source["installed_mva"],
                "routing_capacity_mva": source["routing_capacity_mva"],
                "routing_limit_mw": source["routing_capacity_mva"] * ROUTING_TARGET_LOADING * ROUTING_POWER_FACTOR,
                "baseline_pmax_mw": source["baseline_pmax_mw"],
                "assigned_points": source_point_counts[source_id],
                "allocated_peak_mw": source_peak_mw[source_id],
                "synthetic_peak_within_routing_limit": source_peak_mw[source_id] <= source["routing_capacity_mva"] * ROUTING_TARGET_LOADING * ROUTING_POWER_FACTOR + 1e-9,
                "unique_route_edges": source_edge_counts[source_id],
                "unique_route_length_km": source_lengths[source_id] / 1000.0,
            }
        )
    summary = {
        "method": "multi-source shortest-path forest on the OSM street graph, rooted at seven direct 110/20 kV stations and six legacy 35/10 kV delivery stations",
        "provenance": "Synthetic planning proxy; not an as-built electrical topology.",
        "point_count": len(assignments),
        "connected_point_count": len(assignments),
        "source_specific_route_edges": len(edge_peak_mw),
        "unique_physical_route_edges": len(physical_edges),
        "source_connector_features": len(features) - len(edge_peak_mw),
        "unique_route_length_km": total_length_m / 1000.0,
        "sources": source_summary,
        "primary_station_count": 9,
        "delivery_root_count": len(source_rows),
        "routing_target_loading": ROUTING_TARGET_LOADING,
        "routing_power_factor": ROUTING_POWER_FACTOR,
        "primary_allocated_peak_mw": dict(assigned_primary_peak),
        "primary_routing_limit_mw": primary_capacity_limit,
        "primary_soft_target_mw": primary_target,
        "allocation_basis": "road distance balanced toward EDS 2024 Pmax proportions; targets are scenario priors, not measured coincident loads",
        "legacy_path": "NS2/NS4 (110/35 kV) are shown separately feeding six EDS-listed 35/10 kV stations; they are not treated as direct 20 kV roots.",
    }
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"Created {OUTPUT_GEOJSON.resolve()} with {len(edge_peak_mw)} inferred street-routed segments "
        f"connecting {len(assignments)} synthetic service points."
    )


if __name__ == "__main__":
    main()
