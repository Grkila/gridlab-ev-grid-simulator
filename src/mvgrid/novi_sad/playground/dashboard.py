"""Streamlit interface for the Novi Sad EV hypothesis playground."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import folium
import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml

from mvgrid.novi_sad.playground.service import Service


STATUS_COLOURS = {
    "charging": "#16a34a", "waiting": "#f59e0b", "completed": "#2563eb",
    "departed_shortfall": "#dc2626", "failed": "#dc2626", "overloaded": "#dc2626",
}


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value] if isinstance(value, list) else []


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _result_cases(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases = result.get("cases")
    if isinstance(cases, list):
        return [dict(case) for case in cases if isinstance(case, Mapping)]
    return [dict(result)] if result.get("intervals") else []


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _block_state(case: Mapping[str, Any], interval: Mapping[str, Any]) -> list[dict[str, Any]]:
    static = {str(b.get("id")): dict(b) for b in _records(case.get("blocks"))}
    dynamic = _records(interval.get("blocks"))
    if not dynamic:
        dynamic = _records(case.get("blocks"))
    bad_ids = {str(v.get("block_id")) for v in _records(interval.get("violations")) if v.get("block_id")}
    return [{**static.get(str(block.get("id")), {}), **block,
             "converged": interval.get("converged"), "has_violation": str(block.get("id")) in bad_ids}
            for block in dynamic]


def _block_colour(block: Mapping[str, Any]) -> str:
    if block.get("converged") is False:
        return STATUS_COLOURS["failed"]
    if block.get("has_violation"):
        return STATUS_COLOURS["overloaded"]
    return "#16a34a"


def build_map(blocks: Sequence[Mapping[str, Any]], selected_id: str | None = None) -> str:
    """Return standalone Folium HTML for one interval's block state."""
    located = [b for b in blocks if b.get("lat") is not None and b.get("lon") is not None]
    centre = [45.2671, 19.8335]
    if located:
        centre = [sum(float(b["lat"]) for b in located) / len(located), sum(float(b["lon"]) for b in located) / len(located)]
    fmap = folium.Map(location=centre, zoom_start=12, tiles="OpenStreetMap", control_scale=True)
    # Coordinates and associations come directly from the electrical hierarchy.
    sources = {}
    deliveries = {}
    for block in located:
        source_id = str(block.get("source_id", ""))
        delivery_id = str(block.get("delivery_id", ""))
        if source_id and block.get("source_lat") is not None and block.get("source_lon") is not None:
            sources[source_id] = (float(block["source_lat"]), float(block["source_lon"]))
        if delivery_id and block.get("delivery_lat") is not None and block.get("delivery_lon") is not None:
            deliveries[delivery_id] = (source_id, float(block["delivery_lat"]), float(block["delivery_lon"]))
    for source_id, (lat, lon) in sources.items():
        folium.Marker(
            [lat, lon],
            icon=folium.DivIcon(html='<div aria-hidden="true" style="width:18px;height:18px;transform:rotate(45deg);background:#172554;border:3px solid white;box-shadow:0 0 0 1px #172554"></div>'),
            tooltip=f"{source_id} · HV/MV source",
            popup=folium.Popup(f"<strong>{html.escape(source_id)}</strong><br>Retained supply station", max_width=300),
        ).add_to(fmap)
    for delivery_id, (source_id, lat, lon) in deliveries.items():
        folium.CircleMarker([lat, lon], radius=7, color="#1d4ed8", fill=True, fill_color="#dbeafe",
                            tooltip=f"{delivery_id} · delivery station").add_to(fmap)
        source = sources.get(source_id)
        if source:
            folium.PolyLine([source, [lat, lon]], color="#334155", weight=3, opacity=.8,
                            tooltip=f"{source_id} → {delivery_id} · retained electrical association").add_to(fmap)
    for block in located:
        delivery = deliveries.get(str(block.get("delivery_id", "")))
        if delivery is None:
            continue
        colour = "#b91c1c" if block.get("has_violation") or block.get("converged") is False else "#64748b"
        folium.PolyLine(
            [[delivery[1], delivery[2]], [float(block["lat"]), float(block["lon"])]],
            color=colour, weight=4 if colour == "#b91c1c" else 2, opacity=.8,
            tooltip=f"{block.get('delivery_id')} → {block.get('id')} · simplified electrical link (not physical routing)",
        ).add_to(fmap)
    for block in located:
        bid = str(block.get("id", "Block"))
        counts = _mapping(block.get("counts"))
        exact = ", ".join(f"{key.replace('_', ' ')}: {value}" for key, value in counts.items()) or "No vehicle counts returned"
        failure = "power flow did not converge" if block.get("converged") is False else "configured limit violated" if block.get("has_violation") else "none"
        popup = (f"<strong>{html.escape(bid)}</strong><br>{html.escape(exact)}<br>"
                 f"EV: {html.escape(_fmt(block.get('ev_kw'), 1, ' kW'))}<br>"
                 f"Voltage: {html.escape(_fmt(block.get('voltage_pu'), 3, ' pu'))}<br>"
                 f"Line loading: {html.escape(_fmt(block.get('line_loading_percent'), 1, '%'))}<br>"
                 f"Transformer loading: {html.escape(_fmt(block.get('transformer_loading_percent'), 1, '%'))}<br>"
                 f"Planning capacity: {html.escape(_fmt(block.get('capacity_kw'), 0, ' kW'))}<br>"
                 f"Failure/violation: {html.escape(failure)}")
        radius = 10 if bid == selected_id else 7
        # No block boundary exists in the reduced model; this is an explicitly illustrative catchment.
        folium.Circle([float(block["lat"]), float(block["lon"])], radius=330,
                      color=_block_colour(block), weight=1, fill=True, fill_opacity=.10,
                      tooltip=f"Illustrative catchment · {bid}").add_to(fmap)
        folium.CircleMarker([float(block["lat"]), float(block["lon"])], radius=radius,
                            color="#111827" if bid == selected_id else _block_colour(block), weight=3 if bid == selected_id else 1,
                            fill=True, fill_color=_block_colour(block), fill_opacity=.85,
                            tooltip=f"{bid} · {exact}", popup=folium.Popup(popup, max_width=320)).add_to(fmap)
        # A small, capped set of car glyphs is representative; popup counts remain exact.
        represented = [(state, int(counts.get(state, 0) or 0)) for state in ("charging", "waiting", "completed") if counts.get(state)]
        for offset, (state, count) in enumerate(represented[:3]):
            colour = STATUS_COLOURS.get(state, "#475569")
            car_position = [float(block["lat"]) + .00045 * (offset + 1), float(block["lon"])]
            folium.PolyLine([[float(block["lat"]), float(block["lon"])], car_position], color=colour,
                            weight=1, opacity=.8, dash_array="3 4", tooltip="EV load aggregated at this block node").add_to(fmap)
            folium.Marker(car_position,
                          icon=folium.DivIcon(html=f'<div aria-hidden="true" style="font-size:14px;border:2px solid {colour};border-radius:10px;background:white;line-height:18px;width:22px;text-align:center">🚗</div>'),
                          tooltip=f"Representative {state} EV · exact {state}: {count}").add_to(fmap)
    return fmap.get_root().render()


def _yaml_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return yaml.safe_dump(value or {}, sort_keys=False, allow_unicode=True)


def _error_messages(payload: Mapping[str, Any]) -> list[str]:
    errors = payload.get("errors", [])
    if isinstance(errors, str):
        return [errors]
    if isinstance(errors, list):
        return [str(item.get("message", item)) if isinstance(item, Mapping) else str(item) for item in errors]
    return []


def _render_results(result: Mapping[str, Any]) -> None:
    cases = _result_cases(result)
    if not cases:
        st.info("This run has not returned case results yet.")
        return
    labels = [str(c.get("case_id", f"Case {i + 1}")) for i, c in enumerate(cases)]
    chosen = st.selectbox("Case", labels, key="result_case")
    case = cases[labels.index(chosen)]
    intervals = _records(case.get("intervals"))
    if not intervals:
        st.warning("The selected case has no interval results.")
        metrics = _mapping(case.get("metrics"))
        if metrics:
            st.dataframe(pd.DataFrame([metrics]), use_container_width=True)
        return
    violation_steps = [i for i, item in enumerate(intervals) if item.get("violations") or item.get("converged") is False]
    if violation_steps and st.button("Jump to first violation"):
        st.session_state.time_step = violation_steps[0]
    if len(intervals) == 1:
        step_index = 0
        st.caption("One recorded interval; the run stopped before further time steps.")
    else:
        step_index = st.slider("Time", 0, len(intervals) - 1, min(int(st.session_state.get("time_step", 0)), len(intervals)-1), key="time_step")
    interval = intervals[step_index]
    st.caption(f"Day {step_index // 96 + 1}, {((step_index % 96) * 15) // 60:02d}:{((step_index % 4) * 15):02d} (15-minute interval)")
    blocks = _block_state(case, interval)
    districts = _records(interval.get("districts"))
    transformers = _records(interval.get("transformers"))
    district_ids = [str(d.get("id")) for d in districts]
    selected_district = st.selectbox("Selected district", district_ids, key="selected_district") if district_ids else None
    block_ids = [str(b.get("id")) for b in blocks]
    selected = st.selectbox("Selected block", block_ids, key="selected_block") if block_ids else None

    summary = [
        ("Baseline", _fmt(interval.get("baseline_kw"), 0, " kW")),
        ("EV demand", _fmt(interval.get("ev_kw"), 0, " kW")),
        ("Minimum voltage", _fmt(interval.get("min_voltage_pu"), 3, " pu")),
        ("Max. loading", _fmt(max([v for v in [interval.get("max_line_loading_percent"), interval.get("max_transformer_loading_percent")] if isinstance(v, (int, float))], default=None), 1, "%")),
    ]
    columns = st.columns(4)
    for col, (label, value) in zip(columns, summary):
        col.metric(label, value)
    if interval.get("converged") is False:
        st.error("Power flow did not converge for this interval.")
    stop_reason = _mapping(case.get("stop_reason"))
    if stop_reason:
        trip_step = stop_reason.get("step")
        trip_time = f"Day {int(trip_step) // 96 + 1}, {((int(trip_step) % 96) * 15) // 60:02d}:{((int(trip_step) % 4) * 15):02d}" if isinstance(trip_step, int) else "unknown time"
        trip_violations = _records(stop_reason.get("violations"))
        details = "; ".join(
            f"{v.get('kind', 'violation')} on {v.get('asset_id', v.get('block_id', 'unknown asset'))}: "
            f"{_fmt(v.get('value'), 3)} vs {_fmt(v.get('limit'), 3)}"
            for v in trip_violations
        )
        st.error(f"Safety stop at {trip_time}. {details or 'A configured district or upstream-transformer limit was crossed.'}")
        st.warning("This is partial evidence. The case is incomplete and cannot pass or support a paired comparison.")

    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.caption("Electrical hierarchy on OpenStreetMap: diamonds are retained HV/MV supply stations, blue circles are delivery stations, and load circles are aggregate blocks. Links show returned source → delivery → block associations, not physical routes. Catchments and car glyphs are illustrative; popup and detail counts are exact.")
        components.html(build_map(blocks, selected), height=535, scrolling=False)
    with right:
        selected_block = next((b for b in blocks if str(b.get("id")) == selected), {})
        st.subheader(selected or "Block detail")
        detail = {k: selected_block.get(k) for k in ("source_id", "delivery_id", "delivery_voltage_kv", "baseline_kw", "ev_kw", "total_kw", "voltage_pu", "line_loading_percent", "transformer_loading_percent") if k in selected_block}
        if detail:
            st.dataframe(pd.DataFrame({"Value": {key: _fmt(value, 3) for key, value in detail.items()}}).rename_axis("Measure"), use_container_width=True)
        counts = _mapping(selected_block.get("counts"))
        if counts:
            st.markdown("**Exact vehicle counts**")
            st.dataframe(pd.DataFrame({"Count": counts}).rename_axis("State"), use_container_width=True)
            st.caption("Connected counts describe the full interval. Remaining energy is measured at interval end; departed shortfall is cumulative through that deadline.")
        vehicles = _records(selected_block.get("vehicles"))
        if vehicles:
            st.markdown("**Connected vehicle snapshot**")
            st.dataframe(pd.DataFrame(vehicles), hide_index=True, use_container_width=True)

    frame = pd.DataFrame(intervals)
    demand_cols = [c for c in ("baseline_kw", "ev_kw", "total_kw") if c in frame]
    st.subheader("Demand over time")
    if demand_cols:
        chart = frame[demand_cols].apply(pd.to_numeric, errors="coerce")
        chart["hours"] = [i/4 for i in range(len(frame))]
        chart["time"] = [f"Day {i//96+1} {i%96//4:02d}:{i%4*15:02d}" for i in range(len(frame))]
        curve = chart.melt(id_vars=["hours","time"],var_name="Demand",value_name="kW")
        st.altair_chart(alt.Chart(curve).mark_line().encode(
            x=alt.X("hours:Q",title="Time (HH:MM)",scale=alt.Scale(domain=[0,max(.25,(len(frame)-1)/4)]),axis=alt.Axis(labelExpr="format(floor(datum.value/24)+1, '.0f') + 'd ' + format(floor(datum.value%24), '02.0f') + ':' + format(round((datum.value%1)*60), '02.0f')")),
            y=alt.Y("kW:Q"),color="Demand:N",tooltip=["time:N","Demand:N",alt.Tooltip("kW:Q",format=",.1f")]),use_container_width=True)
    if districts:
        st.subheader("District loading at selected time")
        district_table = pd.DataFrame(districts)
        display_columns = [c for c in ("id", "source_id", "baseline_kw", "ev_kw", "total_kw", "capacity_kw", "headroom_kw", "loading_percent", "provenance", "block_ids", "has_violation") if c in district_table]
        st.dataframe(district_table[display_columns], hide_index=True, use_container_width=True)
        st.caption("District capacities are aggregate planning estimates, not physical MV/LV transformer ratings. Historical results without these fields did not evaluate this constraint.")
    if transformers:
        st.subheader("Transformer loading at selected time")
        transformer_table = pd.DataFrame(transformers)
        display_columns = [c for c in ("id", "hv_kv", "lv_kv", "rating_mva", "p_mw", "q_mvar", "loading_percent", "district_ids", "block_ids", "has_violation") if c in transformer_table]
        st.dataframe(transformer_table[display_columns], hide_index=True, use_container_width=True)
    if selected_district:
        district_curve = []
        transformer_curve = []
        for position, item in enumerate(intervals):
            elapsed = float(item.get("step", position)) / 4.0
            label = f"Day {position // 96 + 1} {((position % 96) * 15) // 60:02d}:{((position % 4) * 15):02d}"
            district = next((d for d in _records(item.get("districts")) if str(d.get("id")) == selected_district), None)
            if district:
                district_curve.append({"elapsed_hours": elapsed, "time": label, "total_kw": district.get("total_kw")})
            for transformer in _records(item.get("transformers")):
                if selected_district in [str(value) for value in transformer.get("district_ids", [])]:
                    transformer_curve.append({"elapsed_hours": elapsed, "time": label, "transformer": transformer.get("id"), "loading_percent": transformer.get("loading_percent")})
        st.subheader(f"{selected_district} and connected transformers")
        if district_curve:
            st.altair_chart(alt.Chart(pd.DataFrame(district_curve)).mark_line().encode(
                x=alt.X("elapsed_hours:Q", title="Time (HH:MM)"), y=alt.Y("total_kw:Q", title="District demand (kW)"),
                tooltip=["time:N", alt.Tooltip("total_kw:Q", format=",.1f")]), use_container_width=True)
        if transformer_curve:
            st.altair_chart(alt.Chart(pd.DataFrame(transformer_curve)).mark_line().encode(
                x=alt.X("elapsed_hours:Q", title="Time (HH:MM)"), y=alt.Y("loading_percent:Q", title="Loading (%)"),
                color="transformer:N", tooltip=["time:N", "transformer:N", alt.Tooltip("loading_percent:Q", format=".1f")]), use_container_width=True)
    heat_rows = []
    for interval_index, item in enumerate(intervals):
        violating = {str(v.get("block_id")) for v in _records(item.get("violations")) if v.get("block_id")}
        for block in _block_state(case, item):
            loading_values = [block.get("line_loading_percent"), block.get("transformer_loading_percent")]
            loading = max((float(value) for value in loading_values if isinstance(value, (int, float))), default=None)
            heat_rows.append({"start_hour": interval_index / 4.0, "end_hour": (interval_index + 1) / 4.0,
                              "time": f"Day {interval_index // 96 + 1} {((interval_index % 96) * 15) // 60:02d}:{((interval_index % 4) * 15):02d}",
                              "block": str(block.get("id")), "loading_percent": loading,
                              "configured_violation": str(block.get("id")) in violating,
                              "converged": bool(item.get("converged", False))})
    heat_frame = pd.DataFrame(heat_rows)
    if not heat_frame.empty and heat_frame["loading_percent"].notna().any():
        st.subheader("Block loading heatmap")
        st.caption("Colour is the larger returned line or transformer loading. Red borders mark configured limit violations.")
        heatmap = alt.Chart(heat_frame).mark_rect().encode(
            x=alt.X("start_hour:Q", title="Time (HH:MM)", axis=alt.Axis(labelOverlap=True, labelAngle=0,labelExpr="format(floor(datum.value/24)+1, '.0f') + 'd ' + format(floor(datum.value%24), '02.0f') + ':' + format(round((datum.value%1)*60), '02.0f')")),
            x2="end_hour:Q",
            y=alt.Y("block:N", title="Block", sort=None),
            color=alt.Color("loading_percent:Q", title="Loading (%)", scale=alt.Scale(scheme="yelloworangered")),
            stroke=alt.condition("datum.configured_violation", alt.value("#b91c1c"), alt.value(None)),
            strokeWidth=alt.condition("datum.configured_violation", alt.value(2), alt.value(0)),
            tooltip=[alt.Tooltip("block:N"), alt.Tooltip("time:N"), alt.Tooltip("loading_percent:Q", format=".1f"),
                     alt.Tooltip("configured_violation:N"), alt.Tooltip("converged:N")],
        ).properties(height=max(260, min(720, 14 * heat_frame["block"].nunique())))
        st.altair_chart(heatmap, use_container_width=True)
    violations = _records(interval.get("violations"))
    if violations:
        st.error(f"{len(violations)} limit violation(s) at this step")
        st.dataframe(pd.DataFrame(violations), hide_index=True, use_container_width=True)

    metrics = _mapping(case.get("metrics"))
    st.subheader("Case verdict and coverage")
    if metrics:
        st.dataframe(pd.DataFrame({"Value": metrics}).rename_axis("Metric"), use_container_width=True)
    else:
        st.caption("No case metrics were returned.")
    for key in ("verdict", "coverage", "assumptions"):
        value = case.get(key, result.get(key))
        if value:
            st.markdown(f"**{key.title()}**")
            st.write(value)
    evaluation = _mapping(result.get("evaluation"))
    if evaluation:
        st.markdown(f"**Experiment verdict: {evaluation.get('verdict', '—')}**")
        st.caption(str(evaluation.get("interpretation", "")))
        assertions = _records(evaluation.get("assertions"))
        if assertions:
            st.dataframe(pd.json_normalize(assertions, sep=" · "), hide_index=True, use_container_width=True)
        st.write("Coverage:", "complete" if evaluation.get("complete") else "incomplete")
    if len(cases) > 1:
        st.subheader("Cases in this run")
        rows = [{"case_id": c.get("case_id"), "strategy": c.get("strategy"), "seed": c.get("seed"),
                 "fleet_size": c.get("fleet_size"), **_mapping(c.get("metrics"))} for c in cases]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def main(service: Service | None = None) -> None:
    st.set_page_config(page_title="EV hypothesis playground", page_icon="⚡", layout="wide")
    st.title("EV hypothesis playground")
    st.caption("Explore synthetic charging hypotheses on the reduced Novi Sad planning proxy. Results are not real travel observations or an as-built grid model.")
    service = service or Service()
    catalog = service.catalog()
    with st.expander("Model scope and assumptions"):
        st.write(catalog.get("fidelity", ""))
        for assumption in catalog.get("assumptions", []):
            st.write(f"• {assumption}")
    if "definition_yaml" not in st.session_state:
        try:
            st.session_state.definition_yaml = _yaml_text(catalog.get("example", {}))
        except Exception as exc:
            st.session_state.definition_yaml = "{}\n"
            st.warning(f"Could not load the example definition: {exc}")

    with st.sidebar:
        st.header("Experiment")
        uploaded = st.file_uploader("Import YAML", type=["yaml", "yml"])
        if uploaded is not None:
            uploaded_bytes = uploaded.getvalue()
            uploaded_hash = hashlib.sha256(uploaded_bytes).hexdigest()
            if st.session_state.get("uploaded_yaml_hash") != uploaded_hash:
                st.session_state.definition_yaml = uploaded_bytes.decode("utf-8")
                st.session_state.uploaded_yaml_hash = uploaded_hash
        experiments = _records(service.list_experiments())
        if experiments:
            selected_exp = st.selectbox("Saved experiments", [str(e.get("experiment_id", e.get("id", ""))) for e in experiments])
            if st.button("Load saved experiment"):
                match = next(e for e in experiments if str(e.get("experiment_id", e.get("id", ""))) == selected_exp)
                st.session_state.definition_yaml = _yaml_text(match.get("definition", match))
                st.rerun()
        raw = st.text_area("Experiment YAML", key="definition_yaml", height=330)
        st.download_button("Download YAML", raw, "ev_experiment.yaml", "application/yaml", use_container_width=True)
        c1, c2 = st.columns(2)
        validate_clicked = c1.button("Validate", use_container_width=True)
        save_clicked = c2.button("Save", use_container_width=True)
        definition = None
        try:
            definition = yaml.safe_load(raw) or {}
            if not isinstance(definition, Mapping):
                raise ValueError("The YAML root must be a mapping.")
        except Exception as exc:
            st.error(f"YAML error: {exc}")
        if validate_clicked and definition is not None:
            try:
                validation = service.validate_experiment(dict(definition))
                errors = _error_messages(validation)
                st.success("Definition is valid.") if not errors and validation.get("valid", True) else st.error("\n".join(errors) or "Definition is invalid.")
            except (ValueError, TypeError) as exc:
                st.error(f"Definition is invalid: {exc}")
        if save_clicked and definition is not None:
            try:
                saved = service.save_experiment(dict(definition))
                st.session_state.experiment_id = saved.get("experiment_id")
                st.success(f"Saved {st.session_state.experiment_id}")
            except (ValueError, TypeError) as exc:
                st.error(f"Could not save: {exc}")
        if st.button("Save and run", type="primary", use_container_width=True, disabled=definition is None):
            try:
                validation = service.validate_experiment(dict(definition))
                errors = _error_messages(validation)
                if errors or validation.get("valid") is False:
                    st.error("\n".join(errors) or "Definition is invalid.")
                else:
                    saved = service.save_experiment(dict(definition))
                    started = service.start_run(str(saved["experiment_id"]))
                    st.session_state.run_id = started.get("run_id")
                    st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(f"Could not start run: {exc}")

    runs = _records(service.list_runs())
    run_ids = [str(r.get("run_id", r.get("id", ""))) for r in runs]
    if run_ids:
        default = run_ids.index(str(st.session_state.get("run_id"))) if str(st.session_state.get("run_id")) in run_ids else 0
        st.session_state.run_id = st.selectbox("Run", run_ids, index=default)
    run_id = st.session_state.get("run_id")
    if not run_id:
        st.info("Save and run an experiment, or choose a saved run to begin.")
        return
    run = service.get_run(str(run_id))
    status = str(run.get("status", "unknown"))
    st.subheader(f"Run {run_id}")
    st.write(f"Status: **{status}**")
    if status == "stopped_on_violation":
        stop = _mapping(run.get("stop_reason"))
        violations = _records(stop.get("violations"))
        assets = ", ".join(str(v.get("asset_id", v.get("block_id", "unknown asset"))) for v in violations)
        st.error(f"Safety stop at step {stop.get('step', 'unknown')}" + (f" on {assets}" if assets else ""))
        st.warning("Coverage is partial. This run is incomplete and cannot be reported as a pass or used for paired comparison.")
    progress_bits = []
    if run.get("completed_cases") is not None:
        total_cases = run.get("total_cases")
        progress_bits.append(f"{run.get('completed_cases')}/{total_cases} cases completed" if total_cases is not None else f"{run.get('completed_cases')} case(s) completed")
    if run.get("current_step") is not None:
        total_steps = run.get("total_steps", run.get("total_steps_per_case"))
        progress_bits.append(f"step {run.get('current_step')}/{total_steps}" if total_steps is not None else f"step {run.get('current_step')}")
    if run.get("phase"):
        progress_bits.append(str(run.get("phase")).replace("_", " "))
    if progress_bits:
        st.caption(" · ".join(progress_bits))
    if run.get("error"):
        st.error(str(run["error"]))
    b1, b2, b3 = st.columns(3)
    if b1.button("Refresh status", use_container_width=True):
        st.rerun()
    if b2.button("Cancel", disabled=status.lower() not in {"running", "starting"}, use_container_width=True):
        try:
            service.cancel_run(str(run_id)); st.rerun()
        except (ValueError, TypeError) as exc:
            st.error(f"Could not cancel: {exc}")
    if b3.button("Resume", disabled=status.lower() not in {"cancelled", "failed", "interrupted", "budget_exceeded"}, use_container_width=True):
        try:
            resumed = service.start_run(str(run.get("experiment_id", st.session_state.get("experiment_id", ""))), resume_run_id=str(run_id))
            st.session_state.run_id = resumed.get("run_id"); st.rerun()
        except (ValueError, TypeError) as exc:
            st.error(f"Could not resume: {exc}")
    try:
        _render_results(service.get_results(str(run_id)))
    except Exception as exc:
        st.warning(f"Results are not available yet: {exc}")

    if len(run_ids) > 1:
        with st.expander("Compare runs"):
            compare_ids = st.multiselect("Runs to compare", run_ids, default=run_ids[:2])
            if st.button("Compare selected runs", disabled=len(compare_ids) < 2):
                try:
                    comparison = service.compare_runs(compare_ids)
                    rows = comparison.get("rows", comparison) if isinstance(comparison, Mapping) else comparison
                    if isinstance(rows, (list, tuple)):
                        st.dataframe(pd.json_normalize(rows, sep=" · "), hide_index=True, use_container_width=True)
                    else:
                        st.json(comparison)
                    if isinstance(comparison, Mapping):
                        st.write("Paired comparison compatible:", comparison.get("paired_compatible", "—"))
                        if comparison.get("differing_fields"):
                            st.caption("Differing experiment fields: " + ", ".join(map(str, comparison["differing_fields"])))
                except (ValueError, TypeError) as exc:
                    st.error(f"Could not compare runs: {exc}")


if __name__ == "__main__":
    main()
