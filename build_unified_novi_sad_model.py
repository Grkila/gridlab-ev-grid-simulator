"""Build the single nine-primary Novi Sad pandapower planning model.

The electrical topology below is deliberately traceable to the generated
planning artifacts. It is suitable for scenario comparison, not an as-built
utility model: street-routed feeder geometry, unverified coordinates and cable
parameters remain explicit assumptions.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import pandapower as pp
import pandas as pd


STATIONS = Path("novi_sad_seeded_substations.json")
INVENTORY = Path("novi_sad_synthetic_transformers.csv")
ASSIGNMENTS = Path("novi_sad_synthetic_feeder_assignments.csv")
FEEDERS = Path("novi_sad_inferred_feeders.geojson")
LEGACY_ROUTES = Path("novi_sad_legacy_35kv_routes.geojson")
FEEDER_SUMMARY = Path("novi_sad_inferred_feeders_summary.json")
OUTPUT_NET = Path("ppnet_novi_sad.json")
OUTPUT_MANIFEST = Path("novi_sad_model_manifest.json")
OUTPUT_RESULTS = Path("novi_sad_powerflow_results.json")
INPUT_MANIFEST = Path("novi_sad_input_manifest.json")

POWER_FACTOR = 0.97
CABLE_MAX_I_KA = 0.319
TARGET_CABLE_LOADING = 0.72


def add_transformer(net, hv_bus, lv_bus, sn_mva, vn_hv_kv, vn_lv_kv, name, station_id, path_kind):
    index = pp.create_transformer_from_parameters(
        net,
        hv_bus=hv_bus,
        lv_bus=lv_bus,
        sn_mva=sn_mva,
        vn_hv_kv=vn_hv_kv,
        vn_lv_kv=vn_lv_kv,
        vk_percent=12.0,
        vkr_percent=0.45,
        pfe_kw=max(18.0, sn_mva * 0.65),
        i0_percent=0.10,
        shift_degree=0.0,
        name=name,
    )
    net.trafo.loc[index, "station_id"] = station_id
    net.trafo.loc[index, "path_kind"] = path_kind
    net.trafo.loc[index, "parameter_provenance"] = "generic planning assumption; rating from EDS table"
    return index


def add_line(
    net, from_bus, to_bus, length_km, vn_kv, downstream_mw, name,
    path_kind, source_id, coords=None,
):
    apparent_mva = downstream_mw / POWER_FACTOR
    capacity_per_circuit = math.sqrt(3.0) * vn_kv * CABLE_MAX_I_KA * TARGET_CABLE_LOADING
    parallel = max(2, math.ceil(apparent_mva / capacity_per_circuit))
    index = pp.create_line_from_parameters(
        net,
        from_bus=from_bus,
        to_bus=to_bus,
        length_km=max(0.001, length_km),
        r_ohm_per_km=0.206,
        x_ohm_per_km=0.115,
        c_nf_per_km=250.0,
        max_i_ka=CABLE_MAX_I_KA,
        parallel=parallel,
        type="cs",
        name=name,
    )
    net.line.loc[index, "source_id"] = source_id
    net.line.loc[index, "path_kind"] = path_kind
    net.line.loc[index, "downstream_design_mw"] = downstream_mw
    net.line.loc[index, "parameter_provenance"] = "generic 150 mm2 urban cable planning assumption"
    if coords:
        net.line_geodata.loc[index, "coords"] = coords
    return index


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def flatten_route_segments(segments):
    """Join contiguous GeoJSON segments into one pandapower coordinate chain."""
    remaining = [[tuple(point) for point in segment] for segment in segments]
    if not remaining:
        return []
    path = remaining.pop(0)

    def same(left, right):
        return abs(left[0] - right[0]) < 1e-10 and abs(left[1] - right[1]) < 1e-10

    while remaining:
        for index, segment in enumerate(remaining):
            if same(path[-1], segment[0]):
                path.extend(segment[1:])
            elif same(path[-1], segment[-1]):
                path.extend(reversed(segment[:-1]))
            elif same(path[0], segment[-1]):
                path = segment[:-1] + path
            elif same(path[0], segment[0]):
                path = list(reversed(segment[1:])) + path
            else:
                continue
            remaining.pop(index)
            break
        else:
            raise ValueError("Legacy route contains disconnected coordinate segments")
    return [list(point) for point in path]


def coordinate_distance_km(left, right):
    """Approximate WGS84 point distance with the haversine formula."""
    lon1, lat1 = map(math.radians, left)
    lon2, lat2 = map(math.radians, right)
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2.0) ** 2
    )
    return 6371.0088 * 2.0 * math.asin(math.sqrt(value))


def route_with_station_endpoints(segments, start, end):
    path = flatten_route_segments(segments)
    forward_gap = coordinate_distance_km(start, path[0]) + coordinate_distance_km(path[-1], end)
    reverse_gap = coordinate_distance_km(start, path[-1]) + coordinate_distance_km(path[0], end)
    if reverse_gap < forward_gap:
        path.reverse()
    if path[0] != list(start):
        path.insert(0, list(start))
    if path[-1] != list(end):
        path.append(list(end))
    return path


def coordinate_chain_length_km(path):
    return sum(coordinate_distance_km(left, right) for left, right in zip(path, path[1:]))


def main():
    station_data = json.loads(STATIONS.read_text(encoding="utf-8"))
    feeder_summary = json.loads(FEEDER_SUMMARY.read_text(encoding="utf-8"))
    feeder_data = json.loads(FEEDERS.read_text(encoding="utf-8"))
    legacy_data = json.loads(LEGACY_ROUTES.read_text(encoding="utf-8"))
    inventory = {row["synthetic_id"]: row for row in read_csv(INVENTORY)}
    assignments = read_csv(ASSIGNMENTS)
    primaries = {row["id"]: row for row in station_data["primary_stations"]}
    secondaries = {row["id"]: row for row in station_data["legacy_secondary_stations"]}
    delivery = {str(row["source_osm_id"]): row for row in feeder_summary["sources"]}

    net = pp.create_empty_network(name="Novi Sad unified nine-primary planning model", sn_mva=100.0)
    primary_output_bus = {}
    ext_grid_by_primary = {}
    for station_id, station in primaries.items():
        hv_bus = pp.create_bus(
            net, vn_kv=110.0, name=f"{station_id} 110 kV", type="b", zone=station_id,
            geodata=(station["lon"], station["lat"]),
        )
        pp.create_ext_grid(net, hv_bus, vm_pu=1.02, name=f"Grid {station_id}")
        ext_grid_by_primary[station_id] = len(net.ext_grid) - 1
        if station["direct_20kv"]:
            mv_bus = pp.create_bus(
                net, vn_kv=20.0, name=f"{station_id} 20 kV", type="b", zone=station_id,
                geodata=(station["lon"], station["lat"]),
            )
            rating = station.get("direct_20kv_mva", station["installed_mva"])
            add_transformer(net, hv_bus, mv_bus, rating, 110.0, 20.0,
                            f"{station_id} 110/20 kV", station_id, "direct_110_20")
            primary_output_bus[station_id] = mv_bus
        else:
            bus_35 = pp.create_bus(
                net, vn_kv=35.0, name=f"{station_id} 35 kV", type="b", zone=station_id,
                geodata=(station["lon"], station["lat"]),
            )
            add_transformer(net, hv_bus, bus_35, station["installed_mva"], 110.0, 35.0,
                            f"{station_id} 110/35 kV", station_id, "legacy_110_35")
            primary_output_bus[station_id] = bus_35

    secondary_output_bus = {}
    legacy_manifest = []
    legacy_by_secondary_name = {f["properties"]["secondary"]: f for f in legacy_data["features"]}
    primary_name_to_id = {row["name"]: row["id"] for row in primaries.values()}
    for secondary_id, secondary in secondaries.items():
        route = legacy_by_secondary_name[secondary["name"]]
        upstream_id = primary_name_to_id[route["properties"]["upstream"]]
        legacy_coords = route_with_station_endpoints(
            route["geometry"]["coordinates"],
            (primaries[upstream_id]["lon"], primaries[upstream_id]["lat"]),
            (secondary["lon"], secondary["lat"]),
        )
        bus_35 = pp.create_bus(
            net, vn_kv=35.0, name=f"{secondary_id} receiving 35 kV", type="b", zone=upstream_id,
            geodata=(secondary["lon"], secondary["lat"]),
        )
        add_line(
            net, primary_output_bus[upstream_id], bus_35,
            coordinate_chain_length_km(legacy_coords), 35.0,
            secondary["installed_mva"] * 0.70, f"{upstream_id}-{secondary_id} inferred 35 kV",
            "legacy_35kv_inferred_route", upstream_id,
            coords=legacy_coords,
        )
        bus_10 = pp.create_bus(
            net, vn_kv=10.0, name=f"{secondary_id} 10 kV", type="b", zone=upstream_id,
            geodata=(secondary["lon"], secondary["lat"]),
        )
        add_transformer(net, bus_35, bus_10, secondary["installed_mva"], 35.0, 10.0,
                        f"{secondary_id} 35/10 kV", secondary_id, "legacy_35_10")
        secondary_output_bus[secondary_id] = bus_10
        legacy_manifest.append({
            "secondary_station_id": secondary_id,
            "primary_station_id": upstream_id,
            "association_status": route["properties"]["upstream_association_status"],
            "route_geometry_status": "inferred",
        })

    delivery_bus = {}
    for source_osm_id, source in delivery.items():
        station_id = source["delivery_station_id"]
        delivery_bus[source_osm_id] = (
            primary_output_bus[station_id]
            if source["delivery_kind"] == "direct_110_20"
            else secondary_output_bus[station_id]
        )

    # Create a distinct street-tree bus namespace for each delivery root. Model
    # the station-to-road connector electrically so the map and pandapower
    # network retain the same inferred path length and impedance.
    feeder_bus = {}
    connector_by_source = {
        str(feature["properties"]["source_osm_id"]): feature
        for feature in feeder_data["features"]
        if feature["properties"]["kind"] == "source_connector"
    }
    for source_osm_id, source in delivery.items():
        root_key = (source_osm_id, int(source["street_graph_root_node"]))
        connector = connector_by_source.get(source_osm_id)
        if connector is None:
            feeder_bus[root_key] = delivery_bus[source_osm_id]
            continue
        coords = connector["geometry"]["coordinates"]
        road_bus = pp.create_bus(
            net,
            vn_kv=float(source["delivery_voltage_kv"]),
            name=f"{source['delivery_station_id']} street root",
            type="n",
            zone=source["primary_station_id"],
            geodata=tuple(coords[-1]),
        )
        connector_index = add_line(
            net,
            delivery_bus[source_osm_id],
            road_bus,
            float(connector["properties"]["length_m"]) / 1000.0,
            float(source["delivery_voltage_kv"]),
            float(source["allocated_peak_mw"]),
            f"{source['delivery_station_id']} station-to-street connector",
            "inferred_source_connector",
            source["primary_station_id"],
            coords=coords,
        )
        net.line.loc[connector_index, "source_osm_id"] = source_osm_id
        feeder_bus[root_key] = road_bus

    feeder_features = [f for f in feeder_data["features"] if f["properties"]["kind"] == "feeder_segment"]
    bus_specs = {}
    for feature in feeder_features:
        props = feature["properties"]
        source_osm_id = str(props["source_osm_id"])
        voltage = float(props["delivery_voltage_kv"])
        zone = props["primary_station_id"]
        coords = feature["geometry"]["coordinates"]
        for node, coord in ((int(props["road_node_u"]), coords[0]), (int(props["road_node_v"]), coords[-1])):
            key = (source_osm_id, node)
            if key not in feeder_bus:
                bus_specs[key] = {
                    "vn_kv": voltage,
                    "name": f"{props['delivery_station_id']} street {node}",
                    "zone": zone,
                    "geodata": tuple(coord),
                }
    if bus_specs:
        keys = list(bus_specs)
        indices = pp.create_buses(
            net,
            len(keys),
            vn_kv=[bus_specs[key]["vn_kv"] for key in keys],
            name=[bus_specs[key]["name"] for key in keys],
            type="n",
            zone=[bus_specs[key]["zone"] for key in keys],
            geodata=[bus_specs[key]["geodata"] for key in keys],
        )
        feeder_bus.update(dict(zip(keys, (int(index) for index in indices))))

    line_specs = []
    for feature in feeder_features:
        props = feature["properties"]
        source_osm_id = str(props["source_osm_id"])
        voltage = float(props["delivery_voltage_kv"])
        downstream_mw = float(props["allocated_peak_mw"])
        apparent_mva = downstream_mw / POWER_FACTOR
        capacity_per_circuit = math.sqrt(3.0) * voltage * CABLE_MAX_I_KA * TARGET_CABLE_LOADING
        line_specs.append({
            "from_bus": feeder_bus[(source_osm_id, int(props["road_node_u"]))],
            "to_bus": feeder_bus[(source_osm_id, int(props["road_node_v"]))],
            "length_km": max(0.001, float(props["length_m"]) / 1000.0),
            "parallel": max(2, math.ceil(apparent_mva / capacity_per_circuit)),
            "name": f"{props['delivery_station_id']} edge {props['road_node_u']}-{props['road_node_v']}",
            "source_id": props["primary_station_id"],
            "downstream_mw": downstream_mw,
            "coords": feature["geometry"]["coordinates"],
        })
    if line_specs:
        line_indices = pp.create_lines_from_parameters(
            net,
            from_buses=[row["from_bus"] for row in line_specs],
            to_buses=[row["to_bus"] for row in line_specs],
            length_km=[row["length_km"] for row in line_specs],
            r_ohm_per_km=0.206,
            x_ohm_per_km=0.115,
            c_nf_per_km=250.0,
            max_i_ka=CABLE_MAX_I_KA,
            parallel=[row["parallel"] for row in line_specs],
            type="cs",
            name=[row["name"] for row in line_specs],
        )
        net.line.loc[line_indices, "source_id"] = [row["source_id"] for row in line_specs]
        net.line.loc[line_indices, "path_kind"] = "inferred_street_feeder"
        net.line.loc[line_indices, "downstream_design_mw"] = [row["downstream_mw"] for row in line_specs]
        net.line.loc[line_indices, "parameter_provenance"] = "generic 150 mm2 aggregated urban cable corridor"
        net.line_geodata = pd.concat(
            [
                net.line_geodata,
                pd.DataFrame(
                    {"coords": pd.Series(
                        [row["coords"] for row in line_specs],
                        index=line_indices,
                        dtype=object,
                    )}
                ),
            ]
        )

    load_manifest = []
    q_factor = math.tan(math.acos(POWER_FACTOR))
    for assignment in assignments:
        synthetic_id = assignment["synthetic_id"]
        source_osm_id = assignment["source_osm_id"]
        node = int(assignment["street_graph_node"])
        item = inventory[synthetic_id]
        p_mw = float(item["peak_demand_mw"])
        load_index = pp.create_load(
            net,
            bus=feeder_bus[(source_osm_id, node)],
            p_mw=p_mw,
            q_mvar=p_mw * q_factor,
            name=synthetic_id,
            type="synthetic_service_point",
        )
        net.load.loc[load_index, "synthetic_id"] = synthetic_id
        net.load.loc[load_index, "annual_mwh"] = float(item["annual_consumption_mwh"])
        net.load.loc[load_index, "primary_station_id"] = assignment["primary_station_id"]
        net.load.loc[load_index, "delivery_station_id"] = assignment["delivery_station_id"]
        net.load.loc[load_index, "delivery_voltage_kv"] = float(assignment["delivery_voltage_kv"])
        net.load.loc[load_index, "provenance"] = "synthetic land-use allocation"
        load_manifest.append({
            "synthetic_id": synthetic_id,
            "load_index": int(load_index),
            "primary_station_id": assignment["primary_station_id"],
            "delivery_station_id": assignment["delivery_station_id"],
            "delivery_voltage_kv": float(assignment["delivery_voltage_kv"]),
            "voltage_path": (
                "110/20 kV -> inferred feeder"
                if float(assignment["delivery_voltage_kv"]) == 20.0
                else "110/35 kV -> inferred 35 kV route -> 35/10 kV -> inferred feeder"
            ),
        })

    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, max_iteration=40,
             tolerance_mva=1e-7, check_connectivity=True)
    pp.to_json(net, OUTPUT_NET)

    source_results = []
    for station_id, ext_index in ext_grid_by_primary.items():
        source_results.append({
            "primary_station_id": station_id,
            "p_mw": float(net.res_ext_grid.at[ext_index, "p_mw"]),
            "q_mvar": float(net.res_ext_grid.at[ext_index, "q_mvar"]),
        })
    total_source_mw = sum(row["p_mw"] for row in source_results)
    total_load_mw = float(net.load.p_mw.sum())
    losses_mw = total_source_mw - total_load_mw
    results = {
        "converged": bool(net.converged),
        "counts": {
            "primary_stations": len(primaries), "delivery_roots": len(delivery),
            "buses": len(net.bus), "lines": len(net.line), "transformers": len(net.trafo),
            "loads": len(net.load), "external_grids": len(net.ext_grid),
        },
        "load_peak_mw": total_load_mw,
        "annual_consumption_mwh": float(net.load.annual_mwh.sum()),
        "source_injection_mw": total_source_mw,
        "losses_mw": losses_mw,
        "losses_pct_of_injection": losses_mw / total_source_mw * 100.0,
        "min_voltage_pu": float(net.res_bus.vm_pu.min()),
        "max_voltage_pu": float(net.res_bus.vm_pu.max()),
        "max_line_loading_pct": float(net.res_line.loading_percent.max()),
        "max_transformer_loading_pct": float(net.res_trafo.loading_percent.max()),
        "source_results": source_results,
        "provenance_warning": "Planning proxy with inferred routes and generic cable parameters; not an as-built EDS model.",
    }
    OUTPUT_RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    manifest = {
        "model": "single unified Novi Sad nine-primary planning model",
        "network_file": str(OUTPUT_NET),
        "station_source": str(STATIONS),
        "load_source": str(INVENTORY),
        "assignment_source": str(ASSIGNMENTS),
        "primary_station_ids": list(primaries),
        "legacy_paths": legacy_manifest,
        "loads": load_manifest,
        "input_snapshot": (
            json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
            if INPUT_MANIFEST.exists()
            else None
        ),
        "assumptions": {
            "power_factor": POWER_FACTOR,
            "feeder_cable": "generic 150 mm2 cable, minimum two parallels, additional parallels sized to 72% design loading",
            "topology": "capacity-balanced radial street proxy",
            "coordinates": station_data["coordinate_warning"],
        },
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Created {OUTPUT_NET.resolve()} with {len(net.load)} loads and {len(net.ext_grid)} active primary sources")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
