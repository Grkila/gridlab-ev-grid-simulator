"""Validate the unified model and compare it with the supplied planning graphic."""
from __future__ import annotations

import json
from numbers import Real
from pathlib import Path

import networkx as nx
import pandapower as pp
import pandapower.topology as top


NET_FILE = Path("ppnet_novi_sad.json")
MANIFEST_FILE = Path("novi_sad_model_manifest.json")
FEEDER_FILE = Path("novi_sad_inferred_feeders.geojson")
REPORT_JSON = Path("novi_sad_validation_report.json")
REPORT_MD = Path("novi_sad_validation_report.md")
EXPECTED_PRIMARY_IDS = {"NS1", "NS2", "NS4", "NS5", "NS6", "NS7", "NS9", "RIM", "FUT"}
BASE_TRANSFORMER_LOADING_LIMIT_PCT = 90.0
IMAGE = {
    "annual_2024_mwh": 1_116_804.0,
    "annual_2025_mwh": 1_147_635.0,
    "annual_change_mwh": 30_831.0,
    "annual_change_pct": 2.76,
    "installed_total_mw": 1_178.0,
    "transmission_mw": 430.0,
    "distribution_mw": 598.0,
    "ts_110_20_mw": 150.0,
    "distribution_20kv_mw": 299.0,
    "distribution_10kv_mw": 179.0,
    "distribution_04kv_mw": 120.0,
    "stated_reserve_mw": 295.0,
    "stated_reserve_pct": 25.0,
}


def solved_metrics(net):
    source = float(net.res_ext_grid.p_mw.sum())
    load = float(net.res_load.p_mw.sum())
    return {
        "converged": bool(net.converged),
        "load_mw": load,
        "source_mw": source,
        "loss_mw": source - load,
        "loss_pct": (source - load) / source * 100.0,
        "min_voltage_pu": float(net.res_bus.vm_pu.min()),
        "max_voltage_pu": float(net.res_bus.vm_pu.max()),
        "max_line_loading_pct": float(net.res_line.loading_percent.max()),
        "max_transformer_loading_pct": float(net.res_trafo.loading_percent.max()),
    }


def acceptable(metrics):
    return (
        metrics["converged"]
        and metrics["min_voltage_pu"] >= 0.95
        and metrics["max_voltage_pu"] <= 1.05
        and metrics["max_line_loading_pct"] < 100.0
        and metrics["max_transformer_loading_pct"] < 100.0
        and 0.0 <= metrics["loss_pct"] <= 10.0
    )


def valid_coordinate_chain(coords):
    return (
        isinstance(coords, (list, tuple))
        and len(coords) >= 2
        and all(
            isinstance(point, (list, tuple))
            and len(point) == 2
            and all(isinstance(value, Real) for value in point)
            for point in coords
        )
    )


def close_point(left, right, tolerance=1e-7):
    return abs(left[0] - right[0]) <= tolerance and abs(left[1] - right[1]) <= tolerance


def main():
    net = pp.from_json(NET_FILE)
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    feeder_data = json.loads(FEEDER_FILE.read_text(encoding="utf-8"))
    pp.runpp(net, algorithm="nr", calculate_voltage_angles=True, max_iteration=40,
             tolerance_mva=1e-7, check_connectivity=True)
    base = solved_metrics(net)

    inventory_ids = {row["synthetic_id"] for row in manifest["loads"]}
    load_ids = set(net.load.synthetic_id.astype(str))
    graph = top.create_nxgraph(net, respect_switches=True, include_out_of_service=False)
    components = list(nx.connected_components(graph))
    source_buses = set(net.ext_grid.bus.astype(int))
    supplied_buses = set()
    for component in components:
        if component.intersection(source_buses):
            supplied_buses.update(component)
    unsupplied_loads = [
        int(load_index) for load_index, load in net.load.iterrows()
        if int(load.bus) not in supplied_buses
    ]

    source_by_id = {
        str(net.ext_grid.at[index, "name"]).replace("Grid ", ""): float(net.res_ext_grid.at[index, "p_mw"])
        for index in net.ext_grid.index
    }
    legacy_transformers = net.trafo[net.trafo.path_kind == "legacy_35_10"]
    legacy_loading = {
        str(row.station_id): float(net.res_trafo.at[index, "loading_percent"])
        for index, row in legacy_transformers.iterrows()
    }
    peak_by_delivery_voltage = {
        str(float(voltage)): float(group.p_mw.sum())
        for voltage, group in net.load.groupby("delivery_voltage_kv")
    }
    peak_20kv_mw = peak_by_delivery_voltage.get("20.0", 0.0)
    peak_10kv_mw = peak_by_delivery_voltage.get("10.0", 0.0)
    expected_connector_ids = {
        str(feature["properties"]["source_osm_id"])
        for feature in feeder_data["features"]
        if feature["properties"]["kind"] == "source_connector"
    }
    connector_lines = net.line[net.line.path_kind == "inferred_source_connector"]
    actual_connector_ids = set(connector_lines.source_osm_id.dropna().astype(str))

    bus_geodata_complete = (
        set(net.bus.index) == set(net.bus_geodata.index)
        and not net.bus_geodata.loc[net.bus.index, ["x", "y"]].isna().any().any()
    )
    line_geodata_complete = set(net.line.index) == set(net.line_geodata.index)
    line_geodata_valid = line_geodata_complete and all(
        valid_coordinate_chain(net.line_geodata.at[index, "coords"])
        for index in net.line.index
    )
    line_endpoints_match_buses = line_geodata_valid and all(
        (
            close_point(
                net.line_geodata.at[index, "coords"][0],
                (net.bus_geodata.at[int(line.from_bus), "x"], net.bus_geodata.at[int(line.from_bus), "y"]),
            )
            and close_point(
                net.line_geodata.at[index, "coords"][-1],
                (net.bus_geodata.at[int(line.to_bus), "x"], net.bus_geodata.at[int(line.to_bus), "y"]),
            )
        )
        or (
            close_point(
                net.line_geodata.at[index, "coords"][0],
                (net.bus_geodata.at[int(line.to_bus), "x"], net.bus_geodata.at[int(line.to_bus), "y"]),
            )
            and close_point(
                net.line_geodata.at[index, "coords"][-1],
                (net.bus_geodata.at[int(line.from_bus), "x"], net.bus_geodata.at[int(line.from_bus), "y"]),
            )
        )
        for index, line in net.line.iterrows()
    )

    validation_checks = {
        "power_flow_converged": base["converged"],
        "exactly_2648_loads": len(net.load) == 2648,
        "unique_traceable_load_ids": len(load_ids) == 2648 and load_ids == inventory_ids,
        "nine_expected_primary_sources": set(source_by_id) == EXPECTED_PRIMARY_IDS,
        "all_nine_sources_active": all(value > 0.001 for value in source_by_id.values()),
        "all_loads_electrically_supplied": not unsupplied_loads,
        "all_source_connectors_modelled_electrically": (
            expected_connector_ids == actual_connector_ids
            and len(connector_lines) == len(expected_connector_ids)
            and connector_lines.in_service.all()
        ),
        "all_buses_have_geodata": bus_geodata_complete,
        "all_lines_have_valid_geodata": line_geodata_valid,
        "line_geodata_endpoints_match_buses": line_endpoints_match_buses,
        "nine_radial_source_islands": (
            len(components) == 9
            and nx.is_forest(graph)
            and all(len(component.intersection(source_buses)) == 1 for component in components)
        ),
        "ns2_ns4_have_no_direct_20kv_transformer": not any(
            row.station_id in {"NS2", "NS4"} and row.path_kind == "direct_110_20"
            for _, row in net.trafo.iterrows()
        ),
        "six_legacy_transformers_active": len(legacy_loading) == 6 and all(value > 0.001 for value in legacy_loading.values()),
        "voltage_within_095_105": base["min_voltage_pu"] >= 0.95 and base["max_voltage_pu"] <= 1.05,
        "no_line_overload": base["max_line_loading_pct"] < 100.0,
        "transformers_within_90pct_planning_margin": (
            base["max_transformer_loading_pct"] <= BASE_TRANSFORMER_LOADING_LIMIT_PCT
        ),
        "losses_nonnegative_below_10pct": 0.0 <= base["loss_pct"] <= 10.0,
    }
    validation_checks = {name: bool(value) for name, value in validation_checks.items()}
    calibrated_input_assertions = {
        "annual_energy_matches_calibration_input": (
            abs(float(net.load.annual_mwh.sum()) - IMAGE["annual_2025_mwh"]) <= 0.01
        ),
        "derived_peak_matches_assumption": (
            abs(float(net.load.p_mw.sum()) - 214.85404109588669) <= 1e-6
        ),
    }
    calibrated_input_assertions = {
        name: bool(value) for name, value in calibrated_input_assertions.items()
    }

    # Uniform-demand hosting test. This tests the inferred electrical proxy;
    # it does not claim the resulting threshold as an EDS operational limit.
    original_p = net.load.p_mw.copy()
    original_q = net.load.q_mvar.copy()
    low, high = 1.0, 1.6
    stress_metrics = base
    for _ in range(10):
        factor = (low + high) / 2.0
        net.load.p_mw = original_p * factor
        net.load.q_mvar = original_q * factor
        try:
            pp.runpp(
                net, algorithm="nr", init="results", calculate_voltage_angles=False,
                max_iteration=40, tolerance_mva=1e-7, check_connectivity=True,
                recycle={"bus_pq": True, "trafo": False, "gen": False},
            )
            metrics = solved_metrics(net)
        except Exception:
            metrics = {"converged": False}
        if metrics.get("converged") and acceptable(metrics):
            low, stress_metrics = factor, metrics
        else:
            high = factor
    net.load.p_mw = original_p
    net.load.q_mvar = original_q

    comparison = {
        "2025_annual_energy": {
            "image_mwh": IMAGE["annual_2025_mwh"],
            "model_mwh": float(net.load.annual_mwh.sum()),
            "difference_mwh": float(net.load.annual_mwh.sum()) - IMAGE["annual_2025_mwh"],
            "interpretation": "Exact by calibration; this is not independent validation.",
        },
        "2024_to_2025_growth": {
            "image_change_mwh": IMAGE["annual_change_mwh"],
            "calculated_pct": (IMAGE["annual_2025_mwh"] / IMAGE["annual_2024_mwh"] - 1.0) * 100.0,
            "model_status": "2024 is not simulated; no independent growth prediction.",
        },
        "delivery_level_capacity_screening": {
            "20kv": {
                "image_capacity_mw": IMAGE["distribution_20kv_mw"],
                "model_peak_mw": peak_20kv_mw,
                "model_peak_as_pct_of_reference": peak_20kv_mw / IMAGE["distribution_20kv_mw"] * 100.0,
            },
            "10kv": {
                "image_capacity_mw": IMAGE["distribution_10kv_mw"],
                "model_peak_mw": peak_10kv_mw,
                "model_peak_as_pct_of_reference": peak_10kv_mw / IMAGE["distribution_10kv_mw"] * 100.0,
            },
            "interpretation": "Screening comparison only: the graphic MW categories are not pandapower equipment-rating sums.",
        },
        "installed_capacity_categories": {
            "image": IMAGE,
            "model_status": "Not scored one-for-one; the graphic uses layered accounting categories that must not be summed against model MVA ratings.",
        },
    }
    passed = all(validation_checks.values())
    report = {
        "status": "INTERNAL_CONSISTENCY_PASS" if passed else "INTERNAL_CONSISTENCY_FAIL",
        "validation_scope": (
            "Internal topology and power-flow acceptance for a synthetic planning proxy; "
            "not independent validation against utility measurements."
        ),
        "validation_checks": validation_checks,
        "calibrated_input_assertions_not_scored": calibrated_input_assertions,
        "base_case": base,
        "peak_by_delivery_voltage_kv": peak_by_delivery_voltage,
        "source_injection_mw": source_by_id,
        "legacy_transformer_loading_pct": legacy_loading,
        "comparison_with_supplied_graphic": comparison,
        "uniform_demand_stress_test": {
            "maximum_acceptable_scale": low,
            "maximum_acceptable_load_mw": 214.85404109588669 * low,
            "binding_case_metrics": stress_metrics,
            "acceptance_limits": "0.95-1.05 pu, line and transformer loading below 100%, losses 0-10%",
            "warning": "Synthetic planning-model threshold, not an EDS operational limit.",
        },
        "honesty_notes": [
            "The 214.854 MW peak is derived from annual energy using an assumed 1.64 peak-to-mean ratio; it is not a measured peak.",
            "Matching 1,147,635 MWh is calibration, not independent validation.",
            "Street feeder routes and cable/impedance parameters are inferred planning assumptions.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD.write_text(
        "# Novi Sad unified-model validation\n\n"
        f"**Result: {report['status']}**\n\n"
        "This is an internal-consistency gate for a synthetic planning proxy, not independent utility validation.\n\n"
        f"- Loads: {len(net.load):,}; primary sources: {len(source_by_id)}\n"
        f"- Base demand: {base['load_mw']:.3f} MW; input: {base['source_mw']:.3f} MW\n"
        f"- Losses: {base['loss_mw']:.3f} MW ({base['loss_pct']:.2f}%)\n"
        f"- Voltage: {base['min_voltage_pu']:.4f}-{base['max_voltage_pu']:.4f} pu\n"
        f"- Maximum line loading: {base['max_line_loading_pct']:.1f}%\n"
        f"- Maximum transformer loading: {base['max_transformer_loading_pct']:.1f}%\n"
        f"- Uniform-demand limit under the stated checks: {low:.3f}x "
        f"({214.85404109588669 * low:.1f} MW)\n\n"
        "The annual 2025 total matches exactly because the synthetic inventory was calibrated to it; "
        "this is not an independent prediction. See the JSON report for all checks and comparison caveats.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
