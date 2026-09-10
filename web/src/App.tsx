import { useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Popup,
  Marker,
} from "react-leaflet";
import L from "leaflet";
import YAML from "yaml";
import { StrategiesWorkspace, StrategyOptionsEditor } from "./Strategies";
import { RLWorkspace, RLExperimentSettings, RLResults, modelControl } from "./RL";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  BatteryCharging,
  Bot,
  CheckCircle2,
  ChevronRight,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Play,
  RefreshCw,
  Save,
  Send,
  Settings2,
  Square,
  Zap,
} from "lucide-react";

type J = Record<string, any>;
const api = async (path: string, init?: RequestInit) => {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || j.detail || `HTTP ${r.status}`);
  return j;
};
const clock = (step: number) => {
  const day = Math.floor(step / 96) + 1,
    m = (step % 96) * 15;
  return `${day > 1 ? `D${day} ` : ""}${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const fmt = (n: any, d = 1) =>
  n !== null && n !== undefined && n !== "" && Number.isFinite(Number(n))
    ? Number(n).toLocaleString(undefined, { maximumFractionDigits: d })
    : "—";
const statusClass = (s = "") =>
  ["completed", "passed"].includes(s)
    ? "ok"
    : ["running", "starting"].includes(s)
      ? "live"
      : ["stopped_on_violation", "failed"].includes(s)
        ? "danger"
        : "muted";

const defaultDefinition: J = {
  schema_version: 1,
  name: "EV charging comparison",
  hypothesis: "Managed charging reduces the city peak.",
  metric_boundary: "city_total",
  observation_contract: "current_state",
  case_origin: "manual",
  assumptions: [
    "Demand shapes are user-supplied seasonal hourly profiles.",
    "Charging windows are planning assumptions.",
  ],
  demand: {
    monthly_energy: 120000,
    unit: "MWh",
    scope: "city_total",
    month: 1,
    days_per_month: 31,
    days: 1,
    annual_growth_rate: 0.03,
    years_ahead: 0,
    scenario: "base",
    variation: "base",
    composition: {
      mode: "preserve_city",
      residential: null,
      commercial: null,
      industrial: null,
    },
  },
  fleet: {
    fleet_size: 100,
    charger_kw: 7.4,
    energy_kwh: 14,
    efficiency: 0.9,
    location_mix: { residential: 0.7, workplace: 0.2, public: 0.1 },
    district_mix: null,
  },
  district_capacity: { scenario: "central", overrides: {} },
  strategies: ["immediate", "capacity_aware"],
  seeds: [1],
  fleet_sizes: null,
  limits: {
    min_voltage_pu: 0.95,
    max_voltage_pu: 1.05,
    max_loading_percent: 100,
  },
  assertions: [],
  max_cases: 100,
  max_runtime_seconds: 600,
  stress_first: true,
  fixed_start_hour: 23,
  stop_on_violation: false,
};

function Metric({
  label,
  value,
  unit,
  icon,
}: {
  label: string;
  value: any;
  unit?: string;
  icon?: any;
}) {
  const I = icon || Activity;
  return (
    <div className="metric">
      <I size={18} />
      <div>
        <span>{label}</span>
        <strong>
          {fmt(value, unit?.trim() === "pu" ? 3 : 1)}
          {value != null && unit}
        </strong>
      </div>
    </div>
  );
}

function NetworkMap({
  network,
  blocks,
  violations,
  step,
}: {
  network: J;
  blocks: J[];
  violations: J[];
  step: number;
}) {
  const nodes: J[] = network.hierarchy_nodes || [],
    edges: J[] = network.hierarchy_edges || [],
    byId = Object.fromEntries(nodes.map((n) => [String(n.id), n]));
  const badBlocks = new Set([
      ...violations.map((v) => String(v.block_id || "")),
      ...violations.flatMap((v) =>
        v.asset_type === "district" ? v.block_ids || [] : [],
      ).map(String),
      ...blocks.filter((b) => b.district_capacity_exceeded).map((b) => String(b.id)),
    ]),
    badAssets = new Set(
      violations.map((v) => `${v.asset_type}:${v.asset_index}`),
    );
  const unknown = violations.some((v) => v.kind === "nonconvergence");
  const badNodes = new Set(
    violations
      .filter((v) => v.asset_type === "bus")
      .map((v) => String(v.asset_index)),
  );
  edges
    .filter((e) => badAssets.has(`${e.kind}:${e.index}`))
    .forEach((e) => {
      badNodes.add(String(e.from_bus));
      badNodes.add(String(e.to_bus));
    });
  const deliveryBuses = new Set(
      blocks.map((b) => String(b.delivery_bus_index)),
    ),
    blockBuses = new Set(blocks.map((b) => String(b.bus_index)));
  return (
    <MapContainer center={[45.2671, 19.8335]} zoom={11} className="map">
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {edges.map((e, i) => {
        const a = byId[String(e.from_bus)],
          b = byId[String(e.to_bus)],
          bad = badAssets.has(
            `${e.kind === "transformer" ? "transformer" : "line"}:${e.index}`,
          );
        return a?.lat != null && b?.lat != null ? (
          <Polyline
            key={i}
            positions={[
              [a.lat, a.lon],
              [b.lat, b.lon],
            ]}
            pathOptions={{
              color: unknown
                ? "#8a9690"
                : bad
                  ? "#d92d20"
                  : e.kind === "transformer"
                    ? "#255c43"
                    : "#7a9f89",
              weight: bad ? 5 : e.kind === "transformer" ? 4 : 2,
              opacity: 0.8,
            }}
          >
            <Popup>
              <b>
                {e.kind} {e.index}
              </b>
              <br />
              {a.name} → {b.name}
              <br />
              {a.vn_kv} kV → {b.vn_kv} kV
            </Popup>
          </Polyline>
        ) : null;
      })}
      {nodes.map((n, i) => {
        const kind =
          Number(n.vn_kv) === 110
            ? "source"
            : deliveryBuses.has(String(n.id))
              ? "delivery"
              : blockBuses.has(String(n.id))
                ? "block"
                : "junction";
        return n.lat != null && n.lon != null ? (
          <CircleMarker
            key={i}
            center={[n.lat, n.lon]}
            radius={
              kind === "source"
                ? 10
                : kind === "delivery"
                  ? 7
                  : kind === "block"
                    ? 5
                    : 3
            }
            pathOptions={{
              color: unknown
                ? "#8a9690"
                : badNodes.has(String(n.id))
                  ? "#d92d20"
                  : kind === "source"
                    ? "#164f36"
                    : kind === "delivery"
                      ? "#287a50"
                      : "#65a77d",
              fillColor: kind === "source" ? "#dff5e7" : "#fff",
              fillOpacity: 1,
              weight: kind === "junction" ? 1 : 3,
            }}
          >
            <Popup>
              <b>{n.name}</b>
              <br />
              {kind} · {n.vn_kv} kV
              <br />
              Bus {n.id}
            </Popup>
          </CircleMarker>
        ) : null;
      })}
      {blocks
        .filter((b) => b.lat != null && b.lon != null)
        .map((b, i) => {
          const bad = badBlocks.has(String(b.id)),
            count = b.counts?.connected || 0,
            pos: [number, number] = [b.lat, b.lon],
            car: [number, number] = [b.lat + 0.0005, b.lon + 0.0005];
          return (
            <span key={"b" + i}>
              <CircleMarker
                center={pos}
                radius={6 + Math.min(8, count / 5)}
                pathOptions={{
                  color: unknown ? "#8a9690" : bad ? "#d92d20" : "#198754",
                  fillColor: unknown ? "#cbd5cf" : bad ? "#f97066" : "#75d09a",
                  fillOpacity: 0.75,
                }}
              >
                <Popup>
                  <b>{b.id}</b>
                  <br />
                  District {b.district_id || "unknown"} · source {b.source_id || "unknown"}
                  <br />
                  Time {clock(step)}
                  <br />
                  EV {fmt(b.ev_kw)} kW
                  <br />
                  Voltage {fmt(b.voltage_pu, 3)} pu
                  <br />
                  Connected cars {count}
                  <br />
                  Charging {b.counts?.charging || 0} · Waiting{" "}
                  {b.counts?.waiting || 0}
                  <br />
                  Completed {b.counts?.completed || 0} · Departed shortfall{" "}
                  {b.counts?.departed_shortfall || 0}
                  {b.district_capacity_exceeded && (
                    <>
                      <br />
                      <b>Estimated district capacity exceeded</b>
                      <br />
                      {fmt(b.district_loading_percent)}% of the configured planning estimate
                    </>
                  )}
                </Popup>
              </CircleMarker>
              {count > 0 && (
                <>
                  <Polyline
                    positions={[pos, car]}
                    pathOptions={{
                      color: "#168650",
                      weight: 1,
                      dashArray: "3 3",
                    }}
                  />
                  <Marker
                    position={car}
                    icon={L.divIcon({
                      className: "car-icon",
                      html: `<span>🚗</span><b>${count}</b>`,
                      iconSize: [38, 22],
                    })}
                  >
                    <Popup>
                      <b>{b.id} vehicle states</b>
                      <br />
                      District {b.district_id || "unknown"} · source {b.source_id || "unknown"}
                      <br />
                      Connected {count}
                      <br />
                      Charging {b.counts?.charging || 0}
                      <br />
                      Waiting {b.counts?.waiting || 0}
                      <br />
                      Completed {b.counts?.completed || 0}
                      <br />
                      Departed shortfall {b.counts?.departed_shortfall || 0}
                    </Popup>
                  </Marker>
                </>
              )}
            </span>
          );
        })}
    </MapContainer>
  );
}

function ExperimentForm({
  definition,
  setDefinition,
  onSave,
  onValidate,
  busy,
  catalog,
  rlModels,
}: {
  definition: J;
  setDefinition: (x: J) => void;
  onSave: () => void;
  onValidate: () => void;
  busy: boolean;
  catalog: J;
  rlModels: J[];
}) {
  const [advanced, setAdvanced] = useState(false),
    [raw, setRaw] = useState(JSON.stringify(definition, null, 2)),
    [rawError, setRawError] = useState("");
  const catalogDistricts: J[] = catalog.districts || [];
  const districtMix: J | null = definition.fleet?.district_mix ?? null;
  const mixTotal = districtMix
    ? Object.values(districtMix).reduce((a: number, x: any) => a + Number(x || 0), 0)
    : 1;
  const updateDistrictCapacity = (id: string, field: string, value: any) => {
    const d = structuredClone(definition);
    d.district_capacity ||= { scenario: "central", overrides: {} };
    d.district_capacity.overrides ||= {};
    if (field === "capacity_kw" && value === undefined) {
      delete d.district_capacity.overrides[id];
      setDefinition(d);
      return;
    }
    d.district_capacity.overrides[id] = {
      capacity_kw:
        field === "capacity_kw"
          ? value
          : d.district_capacity.overrides[id]?.capacity_kw ??
            catalogDistricts.find((row) => row.id === id)?.capacity_kw,
      provenance:
        field === "provenance"
          ? value
          : d.district_capacity.overrides[id]?.provenance ??
            "User-edited planning estimate",
    };
    setDefinition(d);
  };
  const set = (path: string, value: any) => {
    const d = structuredClone(definition);
    const keys = path.split(".");
    let x = d;
    keys.slice(0, -1).forEach((k) => (x = x[k] ||= {}));
    x[keys.at(-1)!] = value;
    setDefinition(d);
  };
  useEffect(() => setRaw(JSON.stringify(definition, null, 2)), [definition]);
  return (
    <div className="form-grid">
      <section className="panel form">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Guided setup</p>
            <h2>Experiment definition</h2>
          </div>
          <button className="ghost" onClick={() => setAdvanced(!advanced)}>
            <Settings2 size={16} />
            {advanced ? "Guided form" : "Advanced JSON"}
          </button>
        </div>
        <div className="import-row">
          <label className="secondary">
            Import YAML
            <input
              type="file"
              accept=".yaml,.yml,text/yaml"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const parsed = YAML.parse(await file.text());
                  const validated = await api("/api/validate", {
                    method: "POST",
                    body: JSON.stringify({ definition: parsed }),
                  });
                  setDefinition(validated.definition);
                  setRawError("");
                } catch (err: any) {
                  setRawError(err.message);
                }
              }}
            />
          </label>
          <button
            className="ghost"
            onClick={() => {
              const blob = new Blob([YAML.stringify(definition)], {
                  type: "text/yaml",
                }),
                url = URL.createObjectURL(blob),
                a = document.createElement("a");
              a.href = url;
              a.download = "ev-experiment.yaml";
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Export YAML
          </button>
        </div>
        {advanced ? (
          <>
            <textarea
              className="json"
              value={raw}
              onChange={(e) => {
                setRaw(e.target.value);
                try {
                  setDefinition(JSON.parse(e.target.value));
                  setRawError("");
                } catch (err: any) {
                  setRawError(err.message);
                }
              }}
            />
            {rawError && (
              <div className="field-error">Invalid JSON: {rawError}</div>
            )}
          </>
        ) : (
          <>
            <label>
              Name
              <input
                value={definition.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </label>
            <label className="wide">
              Hypothesis
              <textarea
                value={definition.hypothesis}
                onChange={(e) => set("hypothesis", e.target.value)}
              />
            </label>
            <label>
              Seasonal preset
              <select
                value=""
                onChange={(e) => {
                  if (!e.target.value) return;
                  const [season, scenario] = e.target.value.split(":");
                  setDefinition({
                    ...definition,
                    demand: {
                      ...definition.demand,
                      monthly_energy: season === "winter" ? 120000 : 76000,
                      unit: "MWh",
                      scope: "city_total",
                      month: season === "winter" ? 1 : 6,
                      days_per_month: season === "winter" ? 31 : 30,
                      days: 1,
                      scenario,
                      variation: "base",
                      annual_growth_rate: 0.03,
                    },
                  });
                }}
              >
                <option value="">Choose a calibrated day…</option>
                <option value="winter:base">Winter base · January</option>
                <option value="winter:worst_case">
                  Winter worst case · +20%
                </option>
                <option value="summer:base">Summer base · June</option>
                <option value="summer:worst_case">
                  Summer worst case · +20%
                </option>
              </select>
            </label>
            <div className="fields">
              <label>
                Demand scenario
                <select
                  value={definition.demand.scenario || "base"}
                  onChange={(e) => set("demand.scenario", e.target.value)}
                >
                  <option value="base">Base</option>
                  <option value="worst_case">Worst-case day (+20%)</option>
                </select>
              </label>
              <label>
                Years ahead
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={definition.demand.years_ahead || 0}
                  onChange={(e) => set("demand.years_ahead", +e.target.value)}
                />
              </label>
              <label>
                Annual growth (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={(definition.demand.annual_growth_rate ?? 0.03) * 100}
                  onChange={(e) =>
                    set("demand.annual_growth_rate", +e.target.value / 100)
                  }
                />
              </label>
              <label>
                Days in calibration month
                <input
                  type="number"
                  min="1"
                  max="31"
                  value={definition.demand.days_per_month}
                  onChange={(e) =>
                    set("demand.days_per_month", +e.target.value)
                  }
                />
              </label>
            </div>
            <p>
              Daily baseline:{" "}
              {fmt(
                ((definition.demand.monthly_energy *
                  (definition.demand.unit === "MWh" ? 1 : 0.001)) /
                  definition.demand.days_per_month) *
                  Math.pow(
                    1 + (definition.demand.annual_growth_rate ?? 0.03),
                    definition.demand.years_ahead || 0,
                  ) *
                  (definition.demand.scenario === "worst_case" ? 1.2 : 1) *
                  ({ base: 1, upper: 1.029, lower: 0.971 }[
                    definition.demand.variation as "base" | "upper" | "lower"
                  ] ?? 1),
                1,
              )}{" "}
              MWh before retained-source scaling. Worst case raises each
              interval by 20%; EV settings remain independently configurable.
            </p>
            <div className="fields">
              <label>
                Monthly energy
                <input
                  type="number"
                  value={definition.demand.monthly_energy}
                  onChange={(e) =>
                    set("demand.monthly_energy", +e.target.value)
                  }
                />
              </label>
              <label>
                Unit
                <select
                  value={definition.demand.unit}
                  onChange={(e) => set("demand.unit", e.target.value)}
                >
                  <option>MWh</option>
                  <option>kWh</option>
                </select>
              </label>
              <label>
                Month
                <input
                  type="number"
                  min="1"
                  max="12"
                  value={definition.demand.month}
                  onChange={(e) => set("demand.month", +e.target.value)}
                />
              </label>
              <label>
                Days
                <input
                  type="number"
                  min="1"
                  max="31"
                  value={definition.demand.days}
                  onChange={(e) => set("demand.days", +e.target.value)}
                />
              </label>
              <label>
                Fleet size
                <input
                  type="number"
                  min="0"
                  value={definition.fleet.fleet_size}
                  onChange={(e) => set("fleet.fleet_size", +e.target.value)}
                />
              </label>
              <label>
                Charger kW
                <input
                  type="number"
                  value={definition.fleet.charger_kw}
                  onChange={(e) => set("fleet.charger_kw", +e.target.value)}
                />
              </label>
              <label>
                Scope
                <select
                  value={definition.demand.scope}
                  onChange={(e) => set("demand.scope", e.target.value)}
                >
                  <option value="city_total">City total</option>
                  <option value="active_sources">Active sources</option>
                </select>
              </label>
              <label>
                Loading limit %
                <input
                  type="number"
                  value={definition.limits.max_loading_percent}
                  onChange={(e) =>
                    set("limits.max_loading_percent", +e.target.value)
                  }
                />
              </label>
            </div>
            <fieldset>
              <legend>Strategies to compare — each runs separately</legend>
              <p>Every selected strategy gets its own case. A failed or stopped case does not cancel the others.</p>
              <div className="checks">
                {(catalog.strategies || ["immediate", "fixed_delay", "randomized_delay", "capacity_aware", "rl"]).map((s: string) => (
                  <label key={s}>
                    <input
                      type="checkbox"
                      checked={definition.strategies.includes(s)}
                      onChange={(e) => {
                        const strategies = e.target.checked ? [...definition.strategies, s] : definition.strategies.filter((x: string) => x !== s);
                        setDefinition({ ...definition, strategies, stop_on_violation: strategies.length > 1 ? false : definition.stop_on_violation });
                      }}
                    />
                    {s.replaceAll("_", " ")}
                  </label>
                ))}
              </div>
            </fieldset>
            {definition.strategies.some((s: string) => ["mpc", "valley_filling"].includes(s)) && <StrategyOptionsEditor value={definition.strategy_options || {}} onChange={strategy_options => setDefinition({ ...definition, strategy_options })} />}
            {definition.strategies.includes("rl") && <RLExperimentSettings value={definition.rl} models={rlModels} onChange={rl => setDefinition({ ...definition, rl })} />}
            <fieldset>
              <legend>Reproducible randomized demand days</legend>
              <label className="rl-check"><input type="checkbox" checked={definition.demand.randomize ?? false} onChange={event => set("demand.randomize", event.target.checked)} /> Randomize demand curves using each experiment seed</label>
              {definition.demand.randomize && <div className="rl-fields">{[["daily_scale_min", "Minimum daily scale", 0.8], ["daily_scale_max", "Maximum daily scale", 1.2], ["shape_noise", "Shape noise", 0.1]].map(([key, label, fallback]) => <label key={key}>{label}<input type="number" min={key === "shape_noise" ? 0 : 0.01} step="any" value={definition.demand[String(key)] ?? fallback} onChange={event => set(`demand.${key}`, +event.target.value)} /></label>)}</div>}
              <p>All strategies in a paired experiment receive the same seeded demand and EV sessions. Use evaluation seeds separate from training.</p>
            </fieldset>
            <fieldset>
              <legend>Low-voltage demand assumptions</legend>
              <p>The image gives capacities but no demand split. These fractions assign existing demand to the downstream 150 MW transformer and 120 MW LV stages without adding it again.</p>
              <label>Baseline demand on LV (%)
                <input aria-label="Baseline demand on LV (%)" type="number" min="0" max="100" value={(definition.network_capacity?.lv_baseline_fraction ?? 0.5) * 100} onChange={e => set("network_capacity.lv_baseline_fraction", +e.target.value / 100)} />
              </label>
              <label>EV charging on LV (%)
                <input aria-label="EV charging on LV (%)" type="number" min="0" max="100" value={(definition.network_capacity?.lv_ev_fraction ?? 1) * 100} onChange={e => set("network_capacity.lv_ev_fraction", +e.target.value / 100)} />
              </label>
              <p>All installed capacity is available. Crossing 75% uses reserve; crossing 100% records a violation.</p>
            </fieldset>
            <fieldset className="capacity-editor">
              <legend>District capacity estimates</legend>
              <p>NS1, NS6 and FUT supplies and hubs are excluded. Their demand is redistributed across the remaining supply areas.</p>
              <div className="capacity-intro">
                <label>
                  Scenario
                  <select
                    value={definition.district_capacity?.scenario || "central"}
                    onChange={(e) => set("district_capacity.scenario", e.target.value)}
                  >
                    <option value="low">Low · 80% of central</option>
                    <option value="central">Central · full aligned rating (reserve usable)</option>
                    <option value="high">High · 120% of central</option>
                  </select>
                </label>
                <p>
                  These are planning estimates, not physical failure or protection-trip limits.
                  Overrides replace the central estimate; the selected scenario factor still applies.
                </p>
              </div>
              <div className="capacity-table-wrap">
                <table className="edit-table">
                  <thead><tr><th>District</th><th>Source</th><th>Central kW</th><th>Central override kW</th><th>Provenance</th></tr></thead>
                  <tbody>{catalogDistricts.map((row) => {
                    const override = definition.district_capacity?.overrides?.[row.id];
                    return <tr key={row.id}>
                      <td>{row.id}</td><td>{row.source_id}</td><td>{fmt(row.capacity_kw)}</td>
                      <td><input aria-label={`${row.id} capacity override`} type="number" min="0.01" placeholder="Use scenario" value={override?.capacity_kw ?? ""} onChange={(e) => updateDistrictCapacity(row.id, "capacity_kw", e.target.value === "" ? undefined : +e.target.value)} /></td>
                      <td><input aria-label={`${row.id} capacity provenance`} placeholder={row.provenance || "Required with override"} value={override?.provenance ?? ""} onChange={(e) => updateDistrictCapacity(row.id, "provenance", e.target.value)} /></td>
                    </tr>;
                  })}</tbody>
                </table>
              </div>
            </fieldset>
            <fieldset className="capacity-editor">
              <legend>EV placement by district</legend>
              <label className="toggle">
                <input type="checkbox" checked={districtMix !== null} onChange={(e) => set("fleet.district_mix", e.target.checked ? Object.fromEntries(catalogDistricts.map((d) => [d.id, 1 / Math.max(1, catalogDistricts.length)])) : null)} />
                <span />
                {districtMix ? "Custom district percentages" : "Automatic placement from the existing geography"}
              </label>
              {districtMix && <>
                <div className="mix-grid">{catalogDistricts.map((row) => <label key={row.id}>{row.id}
                  <input type="number" min="0" max="100" step="0.1" value={fmt((districtMix[row.id] || 0) * 100, 3).replaceAll(",", "")} onChange={(e) => {
                    const shares = { ...districtMix };
                    const value = Number(e.target.value) / 100;
                    if (value === 0) delete shares[row.id];
                    else shares[row.id] = value;
                    set("fleet.district_mix", shares);
                  }} />
                </label>)}</div>
                <div className={Math.abs(mixTotal - 1) < 1e-8 ? "mix-status ok-text" : "mix-status field-error"}>
                  Total: {fmt(mixTotal * 100, 3)}%. Custom weights must total exactly 100%.
                  {mixTotal > 0 && Math.abs(mixTotal - 1) >= 1e-8 && <button type="button" className="ghost" onClick={() => set("fleet.district_mix", Object.fromEntries(Object.entries(districtMix).map(([id, value]) => [id, Number(value) / mixTotal])))}>Normalize explicitly</button>}
                </div>
              </>}
              <p className="state-note">This controls geographic placement. Residential, workplace, and public usage categories remain separate in <code>fleet.location_mix</code>.</p>
            </fieldset>
            <label className="toggle">
              <input
                type="checkbox"
                checked={definition.stop_on_violation}
                onChange={(e) => set("stop_on_violation", e.target.checked)}
              />
              <span />
              Stop the current case when a grid limit is crossed
            </label>
          </>
        )}
        <div className="actions">
          <button
            className="secondary"
            onClick={onValidate}
            disabled={busy || !!rawError || (districtMix !== null && Math.abs(mixTotal - 1) >= 1e-8)}
          >
            <CheckCircle2 size={17} />
            Validate
          </button>
          <button
            className="primary"
            onClick={onSave}
            disabled={busy || !!rawError || (districtMix !== null && Math.abs(mixTotal - 1) >= 1e-8)}
          >
            <Save size={17} />
            Save immutable experiment
          </button>
        </div>
      </section>
      <aside className="panel guidance">
        <p className="eyebrow">Study boundary</p>
        <h3>Planning proxy</h3>
        <p>
          Six supply areas carry all city demand. The 1,178 MW infrastructure sum is
          accounted for through MV ratings and aggregate transmission/LV limits.
          Reserve is usable from 75% to 100%; capacity checks enforce full ratings.
          NS1, NS6 and FUT stations and hubs are removed; their demand is reassigned.
        </p>
        <div className="note">
          <AlertTriangle size={18} />
          <span>
            {definition.stop_on_violation
              ? (definition.strategies.length > 1 ? "Each case stops at its first violation, then the next strategy runs. Disable this to compare full trajectories; stopped cases remain incomplete." : "Safety stop is enabled. This single-strategy experiment stops at its first violation.")
              : "Safety stop is disabled. Violations will be recorded while the full declared trajectory continues."}
          </span>
        </div>
        <dl>
          <dt>Case matrix</dt>
          <dd>strategies × seeds × fleet sizes</dd>
          <dt>Resolution</dt>
          <dd>15 minutes · 96 steps/day</dd>
          <dt>Origin</dt>
          <dd>{definition.case_origin}</dd>
        </dl>
      </aside>
    </div>
  );
}

function CapacityOverview({ alignment, layers }: { alignment?: J; layers?: J[] }) {
  const e = alignment?.estimate;
  if (!e) return null;
  const active = alignment?.operating_model;
  const inventory = [
    { id: "transmission", label: "Transmission supply", mw: e.transmission_mw },
    { id: "mv_20", label: "20 kV delivery", mw: e.distribution_by_voltage_mw["20"] },
    { id: "mv_10", label: "10 kV delivery", mw: e.distribution_by_voltage_mw["10"] },
    { id: "lv_transformers", label: "Downstream transformers · assumed", mw: e.transformer_mw },
    { id: "lv_network", label: "0.4 kV network", mw: e.distribution_by_voltage_mw["0.4"] },
  ];
  return <section className="panel capacity-overview">
    <p className="eyebrow">2025 supplied capacity estimates</p>
    <h2>{fmt(e.reported_total_mw, 0)} MW infrastructure total</h2>
    <p>430 MW transmission + 598 MW distribution + 150 MW transformers. Distribution includes 299 MW at 20 kV, 179 MW at 10 kV and 120 MW at 0.4 kV.</p>
    <p>Power passes through successive stages, so these ratings do not add up to a single supply limit. Transmission feeds the two MV delivery levels; the LV share also passes through downstream transformers and the 0.4 kV network.</p>
    <p><b>75–100% is usable reserve. The limit is 100%.</b> The reported reserve is approximately {fmt(e.reported_reserve_mw, 0)} MW across infrastructure ratings, not an extra pool of power.</p>
    {!active && <p>This historical network predates the aggregate capacity checks; no downstream verdict is available.</p>}
    <div className="capacity-table-wrap"><table className="edit-table">
      <thead><tr><th>Stage</th><th>Full rating MW</th><th>Reserve starts MW</th>{layers && <><th>Demand MW</th><th>Reserve used MW</th><th>Headroom MW</th><th>Status</th></>}</tr></thead>
      <tbody>{inventory.map(row => {
        const live = layers?.find(x => x.id === row.id);
        return <tr key={row.id}><td>{row.label}</td><td>{fmt(row.mw)}</td><td>{fmt(row.mw * (1 - e.reported_reserve_fraction))}</td>{layers && <>
          <td>{live?.demand_kw == null ? "—" : fmt(live.demand_kw / 1000)}</td>
          <td>{live?.reserve_used_kw == null ? "—" : fmt(live.reserve_used_kw / 1000)}</td>
          <td>{live?.headroom_kw == null ? "—" : fmt(live.headroom_kw / 1000)}</td>
          <td>{!live || live.demand_kw == null ? "Unknown" : live.capacity_exceeded ? "Over limit" : live.reserve_used_kw > 0 ? "Using reserve" : "Within rating"}</td>
        </>}</tr>;
      })}</tbody>
    </table></div>
    <p>Transmission uses source power including modelled losses. Downstream stages are aggregate estimates, with editable LV demand shares; they are not a detailed LV power-flow model.</p>
  </section>;
}

function Results({ result, network, loading }: { result: J | null; network: J; loading: boolean }) {
  const cases: J[] = result?.cases || [];
  const [caseIdx, setCaseIdx] = useState(0),
    [step, setStep] = useState(0),
    [section, setSection] = useState("Summary");
  useEffect(() => {
    setCaseIdx(0);
    setStep(0);
  }, [result?.run?.run_id]);
  useEffect(() => {
    if (caseIdx >= cases.length) setCaseIdx(Math.max(0, cases.length - 1));
  }, [cases.length, caseIdx]);
  const c = cases[Math.min(caseIdx, cases.length - 1)],
    ints: J[] = c?.intervals || [],
    it = ints[Math.min(step, Math.max(0, ints.length - 1))] || {},
    staticBlocks = Object.fromEntries(
      (c?.blocks || network.blocks || []).map((b: J) => [String(b.id), b]),
    ),
    blocks = (it.blocks || c?.blocks || []).map((b: J) => ({
      ...staticBlocks[String(b.id)],
      ...b,
    }));
  useEffect(() => {
    if (step >= ints.length) setStep(Math.max(0, ints.length - 1));
  }, [ints.length, step]);
  const data = ints.map((x, i) => ({ ...x, step: i, label: clock(i) }));
  const districts = it.districts || [],
    trafos = it.transformers || [];
  const [district, setDistrict] = useState("");
  useEffect(() => {
    if (districts[0] && !district) setDistrict(districts[0].id);
  }, [districts, district]);
  const districtData = ints.map((x, i) => {
    const d = (x.districts || []).find((z: J) => z.id === district);
    return {
      step: i,
      label: clock(i),
      total_kw: d?.total_kw,
      capacity_kw: d?.capacity_kw,
      loading_percent: d?.loading_percent,
    };
  });
  const trafoIds = new Set<string>(
    trafos
      .filter((t: J) => (t.district_ids || []).includes(district))
      .map((t: J) => String(t.id)),
  );
  const trafoData = ints.map((x, i) =>
    Object.assign(
      { step: i, label: clock(i) },
      ...(x.transformers || [])
        .filter((t: J) => trafoIds.has(String(t.id)))
        .map((t: J) => ({ [String(t.id)]: t.loading_percent })),
    ),
  );
  const frozenNetwork = {
    ...network,
    hierarchy_nodes: c?.hierarchy_nodes || network.hierarchy_nodes,
    hierarchy_edges: c?.hierarchy_edges || network.hierarchy_edges,
  };
  if (!c)
    return (
      <div className="empty">
        <Activity />
        <h2>{loading ? "Loading saved evidence…" : "No case evidence yet"}</h2>
        <p>
          {loading ? "Reading the saved cases and interval measurements." : "Start a saved experiment, then refresh its run while the local worker progresses."}
        </p>
      </div>
    );
  const stop = c.stop_reason || result?.run?.stop_reason;
  const selectedDistrict = districts.find((d: J) => d.id === district) || {};
  const vehicleRows = blocks.map((b: J) => ({
    block_id: b.id,
    connected: b.counts?.connected || 0,
    charging: b.counts?.charging || 0,
    waiting: b.counts?.waiting || 0,
    completed: b.counts?.completed || 0,
    departed_shortfall: b.counts?.departed_shortfall || 0,
  }));
  const vehicleTotals = vehicleRows.reduce(
    (a: J, row: J) => {
      for (const key of [
        "connected",
        "charging",
        "waiting",
        "completed",
        "departed_shortfall",
      ])
        a[key] = (a[key] || 0) + row[key];
      return a;
    },
    { block_id: "All blocks" },
  );
  return (
    <div className="results-workspace">
      <div className="toolbar case-toolbar">
        <span>Charging strategy</span>
        <select
          aria-label="Charging strategy"
          value={caseIdx}
          onChange={(e) => {
            setCaseIdx(+e.target.value);
            setStep(0);
            if (section === "RL controller" && cases[+e.target.value]?.strategy !== "rl") setSection("Summary");
          }}
        >
          {cases.map((x, i) => (
            <option value={i} key={x.case_id}>
              {x.case_id} · {x.strategy} · seed {x.seed}{x.error ? " · failed" : x.complete === false ? " · incomplete" : ""}
            </option>
          ))}
        </select>
        <span className={`badge ${statusClass(result?.run?.status)}`}>
          {result?.run?.status?.replaceAll("_", " ")}
        </span>
        <code>{result?.run?.run_id}</code>
      </div>
      {result?.run?.warning && <p className="notice" role="status">{result.run.warning}</p>}
      {c.error && <div className="trip" role="alert"><AlertTriangle /><div><b>This strategy failed</b><p>{c.error}</p><small>No valid metrics for this case. Other strategies continue; select another case above.</small></div></div>}
      {stop && (
        <div className="trip">
          <AlertTriangle />
          <div>
            <b>Safety stop at {clock(stop.step)}</b>
            <p>
              {(stop.violations || [])
                .slice(0, 3)
                .map(
                  (v: J) => v.kind === "district_capacity_exceeded"
                    ? `Estimated district capacity exceeded — ${v.asset_id}: ${fmt(v.value, 2)} kW demand > ${fmt(v.limit, 2)} kW capacity`
                    : `${v.asset_id}: ${fmt(v.value, 2)} vs ${fmt(v.limit, 2)}`,
                )
                .join(" · ")}
            </p>
            <small>
              Partial evidence · incomplete · excluded from paired comparison
            </small>
          </div>
        </div>
      )}
      <div className="metrics interval-metrics">
        <Metric
          label="Modeled demand"
          value={it.total_kw == null ? null : it.total_kw / 1000}
          unit=" MW"
          icon={Zap}
        />
        <Metric
          label="EV demand"
          value={it.ev_kw}
          unit=" kW"
          icon={BatteryCharging}
        />
        <Metric label="Minimum voltage" value={it.min_voltage_pu} unit=" pu" />
        <Metric
          label="Max transformer"
          value={it.max_transformer_loading_percent}
          unit="%"
        />
      </div>
      <nav className="result-tabs" aria-label="Result views">
        {["Summary", "Network", "Districts", "Evidence", ...(c.strategy === "rl" ? ["RL controller"] : [])].map((name) => <button key={name} aria-pressed={section === name} onClick={() => setSection(name)}>{name}</button>)}
      </nav>
      <div className="time-console">
        <div className="time-readout"><span>Selected interval</span><strong>{clock(step)}</strong></div>
        <div className="time-track">
          <input className="slider" aria-label="Simulation time" type="range" min="0" max={Math.max(0, ints.length - 1)} value={step} disabled={ints.length < 2} onChange={(e) => setStep(+e.target.value)} />
          <div className="ticks"><span>{clock(0)}</span><span>{ints.length} intervals / 15 minutes</span><span>{clock(Math.max(0, ints.length - 1))}</span></div>
        </div>
        <div className="time-buttons"><button aria-label="Previous interval" disabled={step === 0} onClick={() => setStep(step - 1)}>‹</button><button aria-label="Next interval" disabled={step >= ints.length - 1} onClick={() => setStep(step + 1)}>›</button></div>
      </div>
      {section === "RL controller" && (c.strategy === "rl" ? <RLResults currentCase={c} selectedStep={step} /> : <section className="panel"><p>Select an RL case to inspect learned controller evidence, or choose another result view.</p></section>)}
      {section === "Summary" && <div className="summary-layout">

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Demand</p>
              <h2>City demand</h2>
            </div>
          </div>
          <Chart selectedStep={step}
            data={data}
            lines={[
              ["baseline_kw", "#7a9b87", "Baseline"],
              ["ev_kw", "#17a05d", "EV"],
              ["total_kw", "#154c33", "Total"],
            ]}
          />
        </section>
      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Exact interval counts</p>
            <h2>Vehicle states at {clock(step)}</h2>
          </div>
          <span>{vehicleTotals.connected} connected</span>
        </div>
        <div className="metrics">
          <Metric label="Charging" value={vehicleTotals.charging} />
          <Metric label="Waiting" value={vehicleTotals.waiting} />
          <Metric label="Completed" value={vehicleTotals.completed} />
          <Metric
            label="Departed shortfall"
            value={vehicleTotals.departed_shortfall}
          />
        </div>
        <p className="state-note">
          Completed means fully charged while still connected. Departed
          shortfall is cumulative through this interval.
        </p>
        <details className="count-details">
          <summary>Counts by block</summary>
          <DataTable
            rows={[vehicleTotals, ...vehicleRows]}
            cols={[
              "block_id",
              "connected",
              "charging",
              "waiting",
              "completed",
              "departed_shortfall",
            ]}
          />
        </details>
      </section>
      </div>}
      {section === "Network" && <>
        <section className="panel map-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Network state · {clock(step)}</p>
              <h2>Grid at the selected interval</h2>
            </div>
            <span>
              {blocks.reduce(
                (n: number, b: J) => n + (b.counts?.connected || 0),
                0,
              )}{" "}
              connected EVs
            </span>
          </div>
          <NetworkMap
            network={frozenNetwork}
            blocks={blocks}
            violations={it.violations || []}
            step={step}
          />
        </section>      </>}
      {section === "Districts" && <>
      <div className="split">
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">District</p>
              <h2>Delivery load</h2>
            </div>
            <select
              aria-label="District"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
            >
              {districts.map((d: J) => (
                <option key={d.id}>{d.id}</option>
              ))}
            </select>
          </div>
          <Chart selectedStep={step}
            data={districtData}
            lines={[
              ["total_kw", "#168650", "District total kW"],
              ["capacity_kw", "#d97706", "Estimated capacity kW"],
            ]}
          />
          <div className="metrics district-metrics">
            <Metric label="Baseline" value={selectedDistrict.baseline_kw} unit=" kW" />
            <Metric label="EV" value={selectedDistrict.ev_kw} unit=" kW" />
            <Metric label="Capacity estimate" value={selectedDistrict.capacity_kw} unit=" kW" />
            <Metric label="Headroom" value={selectedDistrict.headroom_kw} unit=" kW" />
            <Metric label="District loading" value={selectedDistrict.loading_percent} unit="%" />
          </div>
          <p className="state-note">
            Capacity provenance: {selectedDistrict.capacity_kw == null ? "not available in this saved result" : selectedDistrict.provenance || "saved experiment estimate"}. District capacity is a planning boundary, separate from upstream transformer loading.
          </p>
          <details className="data-disclosure"><summary>All district measurements</summary>
          <DataTable
            rows={districts.map((d: J) => ({
              ...d,
              connected: d.counts?.connected,
              charging: d.counts?.charging,
              waiting: d.counts?.waiting,
              completed: d.counts?.completed,
              departed_shortfall: d.counts?.departed_shortfall,
            }))}
            cols={[
              "id",
              "source_id",
              "baseline_kw",
              "ev_kw",
              "total_kw",
              "capacity_kw",
              "headroom_kw",
              "loading_percent",
              "connected",
              "charging",
              "waiting",
              "completed",
              "departed_shortfall",
              "has_violation",
            ]}
          />
          </details>
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Upstream assets</p>
              <h2>Transformer loading</h2>
            </div>
            <span>{[...trafoIds].length} connected</span>
          </div>
          <Chart selectedStep={step}
            data={trafoData}
            lines={[...trafoIds].map((id, i) => [
              id,
              ["#db7b21", "#287a50", "#4169a1", "#9b59b6"][i % 4],
              id,
            ])}
          />
          <details className="data-disclosure"><summary>All transformer measurements</summary>
          <DataTable
            rows={trafos}
            cols={[
              "id",
              "hv_kv",
              "lv_kv",
              "rating_mva",
              "loading_percent",
              "has_violation",
            ]}
          />
          </details>
        </section>
      </div>
      </>}
      {section === "Network" && <>
      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Thermal overview</p>
            <h2>Block loading heatmap</h2>
          </div>
          <span>15-minute resolution</span>
        </div>
        <Heatmap intervals={ints} />
      </section>
      </>}
      {section === "Evidence" && <>
      <CapacityOverview alignment={c.capacity_alignment} layers={it.capacity_layers} />
      {c.network_capacity && <p>Frozen LV allocation: {fmt(c.network_capacity.lv_baseline_fraction * 100)}% of baseline and {fmt(c.network_capacity.lv_ev_fraction * 100)}% of EV charging. Loads are counted once in the power flow.</p>}
      <section className="panel evidence-summary">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Evidence boundary</p>
            <h2>Case and assertion summary</h2>
          </div>
          <span
            className={`badge ${statusClass(result?.evaluation?.verdict || c.verdict)}`}
          >
            {result?.evaluation?.verdict || c.verdict || "incomplete"}
          </span>
        </div>
        <div className="metrics">
          <Metric
            label="Requested energy"
            value={c.metrics?.requested_energy_kwh}
            unit=" kWh"
          />
          <Metric
            label="Delivered energy"
            value={c.metrics?.delivered_energy_kwh}
            unit=" kWh"
          />
          <Metric
            label="Unmet at departure"
            value={c.metrics?.unmet_energy_kwh}
            unit=" kWh"
          />
          <Metric
            label="Pending at horizon"
            value={c.metrics?.pending_energy_kwh}
            unit=" kWh"
          />
        </div>
        {result?.evaluation?.assertions?.length ? (
          <>
            <DataTable
              rows={result.evaluation.assertions.map((row: J) => ({
                ...row.assertion,
                verdict: row.verdict,
                mean_control: row.mean_control,
                mean_candidate: row.mean_candidate,
                reduction_fraction_observed: row.reduction_fraction,
              }))}
              cols={[
                "type",
                "metric",
                "operator",
                "value",
                "verdict",
                "mean_control",
                "mean_candidate",
                "reduction_fraction_observed",
              ]}
            />
            {result.evaluation.assertions
              .filter((row: J) => row.counterexamples?.length)
              .map((row: J, index: number) => (
                <details key={index} className="counterexamples">
                  <summary>
                    Counterexamples · {row.assertion.metric} ·{" "}
                    {row.counterexamples.length}
                  </summary>
                  <DataTable
                    rows={row.counterexamples.map((example: J) => ({
                      ...example,
                      time:
                        example.first_interval?.[0]?.step != null
                          ? clock(example.first_interval[0].step)
                          : "Departure summary",
                    }))}
                    cols={["case_id", "metric", "time", "value", "threshold"]}
                  />
                  <pre>{JSON.stringify(row.counterexamples, null, 2)}</pre>
                </details>
              ))}
          </>
        ) : (
          <p>
            No assertion evaluation is available for this partial or
            assertion-free run.
          </p>
        )}
      </section>
      </>}
    </div>
  );
}

function Chart({ data, lines, selectedStep }: { data: J[]; lines: any[]; selectedStep?: number }) {
  const max = Math.max(0, data.length - 1),
    ticks = [
      ...new Set(
        Array.from({ length: Math.min(6, data.length || 1) }, (_, i) =>
          Math.round((i * max) / Math.max(1, Math.min(5, data.length - 1))),
        ),
      ),
    ];
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
        >
          <CartesianGrid stroke="#e7eee9" vertical={false} />
          <XAxis
            dataKey="step"
            domain={[0, max]}
            type="number"
            tickFormatter={clock}
            ticks={ticks}
            tick={{ fontSize: 11 }}
          />
          <YAxis domain={[0, "auto"]} tick={{ fontSize: 11 }} />
          <Tooltip
            labelFormatter={(v) => clock(Number(v))}
            formatter={(v: any, n: any) => [fmt(v, 2), n]}
          />
          <Legend />
          {selectedStep != null && <ReferenceLine x={selectedStep} stroke="#16795e" strokeDasharray="4 4" />}
          {lines.map(([key, color, name]) => (
            <Line
              key={key}
              dataKey={key}
              name={name}
              stroke={color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
function DataTable({ rows, cols }: { rows: J[]; cols: string[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c}>{c.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c}>
                  {Array.isArray(r[c])
                    ? r[c].join(", ")
                    : typeof r[c] === "number"
                      ? fmt(r[c], 2)
                      : String(r[c] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Heatmap({ intervals }: { intervals: J[] }) {
  const ids = [
      ...new Set(
        intervals.flatMap((x) => (x.blocks || []).map((b: J) => String(b.id))),
      ),
    ],
    marks = [0, 0.25, 0.5, 0.75, 1].map((x) =>
      Math.round(x * Math.max(0, intervals.length - 1)),
    );
  return (
    <>
      <div className="heat-axis">
        <span />
        {marks.map((x, position) => (
          <b key={position}>{clock(x)}</b>
        ))}
      </div>
      <div className="heat">
        <div className="heat-labels">
          {ids.map((id) => (
            <span key={id}>{id}</span>
          ))}
        </div>
        <div className="heat-grid">
          {ids.map((id) => (
            <div className="heat-row" key={id}>
              {intervals.map((x, i) => {
                const b = (x.blocks || []).find((z: J) => String(z.id) === id),
                  vals = [
                    b?.line_loading_percent,
                    b?.transformer_loading_percent,
                  ]
                    .filter((v: any) => v != null && Number.isFinite(Number(v)))
                    .map(Number),
                  v = vals.length ? Math.max(...vals) : null;
                return (
                  <i
                    key={i}
                    title={`${id} · ${clock(i)} · ${v == null ? "unknown" : fmt(v, 1) + "%"}`}
                    style={{
                      background:
                        v == null
                          ? "#cbd5cf"
                          : `hsl(${Math.max(0, 125 - v * 1.25)} 62% ${Math.max(42, 91 - v * 0.42)}%)`,
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="heat-legend">
        <i />
        Unknown electrical result <span />
        Low → high loading
      </div>
    </>
  );
}

function Chat() {
  const [open, setOpen] = useState(false),
    [id, setId] = useState<string>(),
    [message, setMessage] = useState(""),
    [feed, setFeed] = useState<J[]>([]),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const listener = (event: Event) => { setMessage((event as CustomEvent<string>).detail); setOpen(true); };
    window.addEventListener("strategy-chat", listener);
    return () => window.removeEventListener("strategy-chat", listener);
  }, []);
  const send = async () => {
    if (busy || !message.trim()) return;
    setBusy(true);
    setFeed((f) => [...f, { role: "user", content: message }]);
    try {
      const x = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message, chat_id: id }),
      });
      setId(x.chat_id);
      setFeed((f) => [...f, ...(x.events || [])]);
      setMessage("");
    } catch (e: any) {
      setFeed((f) => [...f, { type: "error", text: e.message }]);
      setBusy(false);
    }
  };
  useEffect(() => {
    if (!id || !busy) return;
    const t = setInterval(async () => {
      try {
        const x = await api(`/api/chat/${id}`);
        const combined = [...(x.messages || []), ...(x.events || []),
          ...(x.error ? [{ event_id: `${x.chat_id}-terminal-error`, type: 'error', text: `${x.status}: ${x.error}` }] : [])];
        setFeed(
          Array.from(
            new Map(
              combined.map((e: J, i: number) => [
                e.id || e.event_id || JSON.stringify(e) || i,
                e,
              ]),
            ).values(),
          ),
        );
        if (!["running", "starting"].includes(x.status)) setBusy(false);
      } catch (e: any) {
        setFeed((f) => [...f, { type: "error", text: e.message }]);
        setBusy(false);
      }
    }, 1200);
    return () => clearInterval(t);
  }, [id, busy]);
  if (!open)
    return (
      <button className="chat-launch" onClick={() => setOpen(true)}>
        <Bot size={19} />
        Codex CLI chat
      </button>
    );
  return (
    <aside className="chat">
      <div className="chat-head">
        <Bot />
        <div>
          <b>Codex experiment assistant</b>
          <small>
            {busy ? "Working with live tool events" : "Ready to send"}
          </small>
        </div>
        <button
          title={busy ? "Cancel Codex task" : "Minimize chat"}
          onClick={() =>
            busy && id
              ? api(`/api/chat/${id}/cancel`, {
                  method: "POST",
                  body: "{}",
                }).then(() => setBusy(false))
              : setOpen(false)
          }
        >
          <Square size={14} />
        </button>
      </div>
      <div className="feed">
        {!feed.length && (
          <div className="welcome">
            <MessageSquare />
            <b>Ask about this study</b>
            <p>
              Draft an experiment, inspect a stopped run, or compare evidence.
              Tool calls appear here as they happen.
            </p>
          </div>
        )}
        {feed.map((e, i) => {
          const item = e.item || {},
            tool = item.type === "mcp_tool_call";
          return (
            <div key={i} className={`event ${e.type || e.role || "tool"}`}>
              <small>
                {tool
                  ? `${item.server || "MCP"} · ${item.tool} · ${item.status || "event"}`
                  : e.type || e.role || "event"}
              </small>
              {tool ? (
                <details>
                  <summary>Tool call</summary>
                  <pre>{JSON.stringify(item.arguments, null, 2)}</pre>
                  {item.result && (
                    <pre>
                      {typeof item.result === "string"
                        ? item.result
                        : JSON.stringify(item.result, null, 2)}
                    </pre>
                  )}
                </details>
              ) : (
                <p>
                  {e.content ||
                    e.text ||
                    e.message ||
                    item.text ||
                    JSON.stringify(e)}
                </p>
              )}
            </div>
          );
        })}
      </div>
      <div className="strategy-stages"><button className="ghost" disabled={busy} onClick={() => setMessage("STRATEGY PROPOSE\nname: new_strategy\nidea: Describe your charging idea.\nresearch: adaptation")}>Propose strategy</button><button className="ghost" disabled={busy} onClick={() => setMessage("Help me specify and compare a new charging strategy using the strategy workflow. Inspect the available strategies and saved scenarios first.")}>Plan comparison</button></div>
      <div className="composer">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          aria-label="Message to Codex"
          placeholder="Ask about experiments or paste a STRATEGY command…"
        />
        <button aria-label="Send message" onClick={send} disabled={busy || !message.trim()}>
          <Send size={17} />
        </button>
      </div>
    </aside>
  );
}

export default function App() {
  const [view, setView] = useState("overview"),
    [catalog, setCatalog] = useState<J>({}),
    [network, setNetwork] = useState<J>({}),
    [experiments, setExperiments] = useState<J[]>([]),
    [rlModels, setRLModels] = useState<J[]>([]),
    [runs, setRuns] = useState<J[]>([]),
    [definition, setDefinition] = useState<J>(defaultDefinition),
    [runId, setRunId] = useState<string>(),
    [result, setResult] = useState<J | null>(null),
    [loadingResults, setLoadingResults] = useState(false),
    [compareIds, setCompareIds] = useState<string[]>([]),
    [comparison, setComparison] = useState<J | null>(null),
    [comparing, setComparing] = useState(false),
    [compareError, setCompareError] = useState(""),
    [notice, setNotice] = useState(""),
    [runName, setRunName] = useState(""),
    [deletedRun, setDeletedRun] = useState<string>(),
    [busy, setBusy] = useState(false);
  const load = async () => {
    try {
      const [c, n, e, r] = await Promise.all([
        api("/api/catalog"),
        api("/api/network"),
        api("/api/experiments"),
        api("/api/runs"),
      ]);
      setCatalog(c);
      setNetwork(n);
      // Loading server catalogs must not replace an experiment draft already edited by the user.
      setExperiments(Array.isArray(e) ? e : e.experiments || []);
      setRuns(Array.isArray(r) ? r : r.runs || []);
    } catch (e: any) {
      setNotice(e.message);
    }
  };
  useEffect(() => {
    load();
    api("/api/rl/catalog").then(data => setRLModels(data.models || [])).catch(() => {});
  }, []);
  const openRun = async (id: string) => {
    setRunId(id);
    setRunName(runs.find((r) => r.run_id === id)?.name || id);
    setResult(null);
    setLoadingResults(!!id);
    setView("results");
    if (!id) return;
    try {
      setResult(await api(`/api/runs/${id}/results`));
    } catch (e: any) {
      setNotice(e.message);
    } finally { setLoadingResults(false); }
  };
  useEffect(() => {
    if (!runId) return;
    const run = runs.find((r) => r.run_id === runId);
    if (!run || !["running", "starting"].includes(run.status)) return;
    const t = setInterval(async () => {
      const s = await api(`/api/runs/${runId}`);
      setRuns((x) => x.map((r) => (r.run_id === runId ? s : r)));
      try {
        setResult(await api(`/api/runs/${runId}/results`));
      } catch {}
    }, 1500);
    return () => clearInterval(t);
  }, [runId, runs]);
  const validate = async () => {
    setBusy(true);
    try {
      const x = await api("/api/validate", {
        method: "POST",
        body: JSON.stringify({ definition }),
      });
      setDefinition(x.definition || definition);
      setNotice(
        `Valid · ${x.cases?.length || 0} cases · up to ${fmt(x.estimated_power_flows, 0)} power flows`,
      );
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    setBusy(true);
    try {
      const x = await api("/api/experiments", {
        method: "POST",
        body: JSON.stringify({ definition }),
      });
      setExperiments((v) => [
        x,
        ...v.filter((e) => e.experiment_id !== x.experiment_id),
      ]);
      setNotice(`Saved immutable ${x.experiment_id}`);
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  };
  const start = async (id: string) => {
    try {
      const x = await api("/api/runs", {
        method: "POST",
        body: JSON.stringify({ experiment_id: id }),
      });
      setRuns((v) => [x, ...v.filter((r) => r.run_id !== x.run_id)]);
      openRun(x.run_id);
    } catch (e: any) {
      setNotice(e.message);
    }
  };
  const current = runs.find((r) => r.run_id === runId);
  const manageRun = async (action: "rename" | "delete" | "restore", id: string) => {
    setBusy(true);
    try {
      const updated = await api(`/api/runs/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify(action === "rename" ? { name: runName } : {}),
      });
      if (action === "delete") {
        setDeletedRun(id);
        setRuns((items) => items.filter((r) => r.run_id !== id));
        setRunId(undefined);
        setResult(null);
        setCompareIds((ids) => ids.filter((value) => value !== id));
        setComparison(null);
        setNotice("Run deleted. Its saved evidence can be restored with Undo.");
      } else {
        setRuns((items) => [updated, ...items.filter((r) => r.run_id !== id)]);
        if (action === "restore") setDeletedRun(undefined);
        if (action === "rename") setRunName(updated.name);
        setNotice(action === "rename" ? "Run renamed." : "Run restored.");
      }
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={`app ${view === "results" ? "results-page" : ""}`}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="nav">
        <div className="brand">
          <span>
            <Zap />
          </span>
          <div>
            <b>GridLab</b>
            <small>EV hypothesis studio</small>
          </div>
        </div>
        <nav>
          {[
            ["overview", LayoutDashboard],
            ["experiments", FlaskConical],
            ["strategies", BatteryCharging],
            ["rl", Bot],
            ["network", GitBranch],
            ["results", Activity],
          ].map(([v, I]: any) => (
            <button
              className={view === v ? "active" : ""}
              onClick={() => { setView(v); window.scrollTo(0, 0); if (v === "results" && !runId && runs.length) openRun(runs[0].run_id); }}
              key={v}
            >
              <I size={19} />
              {v === "rl" ? "RL workspace" : v}
            </button>
          ))}
        </nav>
        <div className="model">
          <i />
          <span>
            Local model<b>{catalog.backend || "Connecting…"}</b>
          </span>
        </div>
      </aside>
      <main id="main-content" tabIndex={-1}>
        <header>
          <div>
            <p className="eyebrow">Novi Sad planning proxy</p>
            <h1>{view === "rl" ? "RL workspace" : view[0].toUpperCase() + view.slice(1)}</h1>
          </div>
          <div className="header-actions">
            <button className="ghost" onClick={load}>
              <RefreshCw size={16} />
              Refresh
            </button>
            {current && view !== "results" && (
              <span className={`badge ${statusClass(current.status)}`}>
                {current.status.replaceAll("_", " ")}
              </span>
            )}
          </div>
        </header>
        {notice && (
          <div className="notice" role="status" aria-live="polite">
            {notice}
            <button className="dismiss-notice" aria-label="Dismiss notification" onClick={() => setNotice("")}>×</button>
          </div>
        )}
        {deletedRun && <div className="notice" role="status">
          Run removed from the list.
          <button disabled={busy} onClick={() => manageRun("restore", deletedRun)}>Undo delete</button>
        </div>}
        {view === "overview" && (
          <>
            <div className="hero">
              <div>
                <p className="eyebrow">Evidence before confidence</p>
                <h2>
                  EV charging studies
                </h2>
                <p>
                  Create a scenario, run charging strategies, and inspect demand and grid limits at each 15-minute interval.
                </p>
                <button
                  className="primary"
                  onClick={() => setView("experiments")}
                >
                  <FlaskConical />
                  Design an experiment
                  <ChevronRight />
                </button>
              </div>
              <div className="hero-grid">
                <Metric
                  label="Retained supplies"
                  value={
                    network.hierarchy_nodes?.filter(
                      (n: J) => Number(n.vn_kv) === 110,
                    ).length
                  }
                />
                <Metric
                  label="Transformers"
                  value={
                    network.hierarchy_edges?.filter(
                      (e: J) => e.kind === "transformer",
                    ).length
                  }
                />
                <Metric
                  label="Delivery blocks"
                  value={network.blocks?.length}
                />
                <Metric label="Time resolution" value={15} unit=" min" />
              </div>
            </div>
            <CapacityOverview alignment={catalog.capacity_alignment} />
            <div className="split">
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">Recent evidence</p>
                    <h2>Runs</h2>
                  </div>
                </div>
                <DataTable
                  rows={runs.slice(0, 8)}
                  cols={[
                    "name",
                    "run_id",
                    "status",
                    "completed_cases",
                    "total_cases",
                    "verdict",
                  ]}
                />
              </section>
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">Model boundary</p>
                    <h2>What this study represents</h2>
                  </div>
                </div>
                <p>{catalog.fidelity}</p>
                <ul>
                  {(catalog.assumptions || []).map((a: string) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </section>
            </div>
          </>
        )}
        {view === "experiments" && (
          <>
            <ExperimentForm
              {...{
                definition,
                setDefinition,
                onSave: save,
                onValidate: validate,
                busy,
                catalog,
                rlModels,
              }}
            />
            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="eyebrow">Immutable catalog</p>
                  <h2>Saved experiments</h2>
                </div>
              </div>
              <div className="cards">
                {experiments.map((e) => (
                  <article key={e.experiment_id}>
                    <code>{e.experiment_id}</code>
                    <h3>{e.definition?.name}</h3>
                    <p>{e.definition?.hypothesis}</p>
                    <button
                      className="primary"
                      onClick={() => start(e.experiment_id)}
                    >
                      <Play size={15} />
                      Run
                    </button>
                  </article>
                ))}
              </div>
            </section>
          </>
        )}
        {view === "strategies" && <StrategiesWorkspace experiments={experiments} onPrepared={load} onUse={id => {
          setDefinition(previous => ({ ...previous, strategies: [...new Set([...previous.strategies, id])], stop_on_violation: false }));
          setView("experiments");
          setNotice(id === "rl" ? "Select a trained model in the experiment settings." : "Controller added to your experiment draft.");
        }} />}
        {view === "rl" && <RLWorkspace experiments={experiments} draft={definition}
          onSaved={experiment => setExperiments(previous => [experiment, ...previous.filter(row => row.experiment_id !== experiment.experiment_id)])}
          onModels={setRLModels}
          onUseModel={model => {
            setDefinition(previous => ({ ...previous, strategies: [...new Set([...previous.strategies, "rl"])], stop_on_violation: false, rl: modelControl(model) }));
            setView("experiments");
            setNotice(`Added ${model.name || model.model_id} to the current draft. Save this experiment, then run its saved revision.`);
          }} />}
        {view === "network" && (
          <section className="panel full-map">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Retained topology</p>
                <h2>Supply and delivery hierarchy</h2>
              </div>
              <span>
                {network.excluded_sources?.length || 0} excluded sources ·{" "}
                {fmt((network.retained_demand_fraction || 0) * 100, 1)}%
                retained demand
              </span>
            </div>
            <NetworkMap
              network={network}
              blocks={network.blocks || []}
              violations={[]}
              step={0}
            />
          </section>
        )}
        {view === "results" && (
          <>
            <div className="run-picker">
              <select
                aria-label="Choose a run"
                value={runId || ""}
                onChange={(e) => openRun(e.target.value)}
              >
                <option value="">Choose a run…</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.name || r.run_id} · {r.name && r.name !== r.run_id ? `${r.run_id} · ` : ""}{r.status}
                  </option>
                ))}
              </select>
              {runId && (
                <button className="ghost" onClick={() => openRun(runId)}>
                  <RefreshCw size={16} />
                  Refresh evidence
                </button>
              )}
              {current && ["running", "starting"].includes(current.status) && (
                <button
                  className="secondary"
                  onClick={async () => {
                    await api(`/api/runs/${current.run_id}/cancel`, {
                      method: "POST",
                      body: "{}",
                    });
                    await load();
                  }}
                >
                  <Square size={15} />
                  Cancel
                </button>
              )}
              {current &&
                [
                  "cancelled",
                  "failed",
                  "interrupted",
                  "budget_exceeded",
                ].includes(current.status) && (
                  <button
                    className="primary"
                    onClick={async () => {
                      const x = await api("/api/runs", {
                        method: "POST",
                        body: JSON.stringify({
                          experiment_id: current.experiment_id,
                          resume_run_id: current.run_id,
                        }),
                      });
                      setRuns((v) => [
                        x,
                        ...v.filter((r) => r.run_id !== x.run_id),
                      ]);
                      openRun(x.run_id);
                    }}
                  >
                    <Play size={15} />
                    Resume
                  </button>
                )}
            </div>
            {current && <details className="run-management"><summary>Manage run</summary>
              <form className="run-picker" onSubmit={(e) => { e.preventDefault(); manageRun("rename", current.run_id); }}>
                <label>Run name<input aria-label="Run name" value={runName} maxLength={120} onChange={(e) => setRunName(e.target.value)} /></label>
                <button type="submit" disabled={busy || !runName.trim()}>Rename run</button>
                <button type="button" disabled={busy || ["starting", "running"].includes(current.status)}
                  title={["starting", "running"].includes(current.status) ? "Cancel the run and wait for it to stop first" : "Remove this run from the list; Undo is available"}
                  onClick={() => manageRun("delete", current.run_id)}>Delete run</button>
              </form>
            </details>}
            <Results result={result} network={network} loading={loadingResults} />
            {runs.length > 1 && (
              <details className="comparison-panel"><summary>Compare runs</summary>
                <div className="panel-head">
                  <div>
                    <p className="eyebrow">Controlled comparison</p>
                    <h2>Compare completed evidence</h2>
                  </div>
                </div>
                <p>Choose 2–8 runs. Each checkbox adds or removes a run from the comparison.</p>
                <fieldset className="compare-run-list" disabled={comparing}>
                  <legend>Runs to compare</legend>
                  {runs.map((r) => <label key={r.run_id}>
                    <input type="checkbox" aria-label={`Compare ${r.name || r.run_id} (${r.run_id})`}
                      checked={compareIds.includes(r.run_id)}
                      disabled={!compareIds.includes(r.run_id) && compareIds.length >= 8}
                      onChange={(event) => {
                        setCompareIds((ids) => event.target.checked ? [...ids, r.run_id] : ids.filter((id) => id !== r.run_id));
                        setComparison(null);
                        setCompareError("");
                      }} />
                    <span><strong>{r.name || r.run_id}</strong><small>{r.run_id}</small></span>
                    <span className={`badge ${statusClass(r.status)}`}>{r.status.replaceAll("_", " ")}</span>
                  </label>)}
                </fieldset>
                <div className="compare-controls">
                  <button className="primary" disabled={comparing || compareIds.length < 2 || compareIds.length > 8}
                    onClick={async () => {
                      setComparing(true);
                      setCompareError("");
                      setComparison(null);
                      try {
                        setComparison(await api("/api/compare", { method: "POST", body: JSON.stringify({ run_ids: compareIds }) }));
                      } catch (error: any) {
                        setCompareError(error.message || "Comparison failed. Refresh the run list and try again.");
                      } finally { setComparing(false); }
                    }}>
                    {comparing ? "Comparing…" : "Compare selected"}
                  </button>
                  <span role="status" aria-live="polite">{comparing ? "Loading comparison…" : `${compareIds.length} of 8 selected`}</span>
                </div>
                {compareError && <p className="trip" role="alert">{compareError} Refresh the run list and try again.</p>}
                {comparison && (
                  <>
                    <div
                      className={`note ${comparison.complete ? "" : "trip"}`}
                    >
                      {comparison.paired_compatible
                        ? "Runs are compatible for paired comparison."
                        : comparison.complete
                          ? "Descriptive comparison: these completed runs have different saved inputs or implementation versions, so they are not a controlled pair."
                          : "Partial comparison: one or more runs are incomplete. Their recorded results are shown below, but cannot establish a paired result."}
                    </div>
                    <DataTable
                      rows={(comparison.rows || []).map((row: J) => ({
                        ...row,
                        run_name: runs.find((run) => run.run_id === row.run_id)?.name || row.run_id,
                        ...row.metrics,
                      }))}
                      cols={[
                        "run_name",
                        "run_id",
                        "case_id",
                        "strategy",
                        "seed",
                        "fleet_size",
                        "run_status",
                        "complete",
                        "peak_demand_kw",
                      ]}
                    />
                  </>
                )}
              </details>
            )}
          </>
        )}
      </main>
      <Chat />
    </div>
  );
}
