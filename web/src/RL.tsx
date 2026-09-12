import { useEffect, useMemo, useRef, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";
import { Bot, Play, RefreshCw, Save, Square } from "lucide-react";
import "./rl.css";
import { ContinuousRL } from "./ContinuousRL";
import { PPODemo } from "./PPODemo";
import { usePresentationCue } from './presentation/bridge';

type J = Record<string, any>;
export const rewardDefaults = { delivery: 1, shortfall: 10, capacity: 1000, energy: 1000, switching: 0.05, peak: 0.1, intervention: 10 };
export const modelControl = (model: J) => ({ model_id: model.model_id, safety_shield: model.training_config?.safety_shield ?? true, daily_energy_limit_kwh: model.training_config?.daily_energy_limit_kwh ?? null, reward: { ...rewardDefaults, ...model.training_config?.reward } });
const trainingDefaults: J = { episodes: 20, seed: 10000, learning_rate: 0.01, gamma: 0.99, max_runtime_seconds: 600, reward: rewardDefaults, safety_shield: true, daily_energy_limit_kwh: null, demand_scale_min: 0.8, demand_scale_max: 1.2, shape_noise: 0.1 };
const rewardLabels: Record<string, string> = { delivery: "Energy delivered", shortfall: "Departure shortfall", capacity: "Capacity violation", energy: "Daily energy excess", switching: "Switching", peak: "Peak demand", intervention: "Shield intervention" };
const palette = ["#16795e", "#c54936", "#ae458b", "#d4801b", "#3662a3", "#69733e", "#674ab0"];
const active = (status: string) => ["queued", "starting", "running", "cancelling"].includes(status);
const number = (value: any, digits = 2) => value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
const time = (step: number) => `${step >= 96 ? `D${Math.floor(step / 96) + 1} ` : ""}${String(Math.floor((step % 96) / 4)).padStart(2, "0")}:${String((step % 4) * 15).padStart(2, "0")}`;
const request = async (path: string, init?: RequestInit) => {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : JSON.stringify(data.error || data.detail || `HTTP ${response.status}`));
  return data;
};
const readTrainingDraft = () => {
  try { return JSON.parse(sessionStorage.getItem("gridlab-rl-training-draft-v1") || "null"); }
  catch { return null; }
};

// Keep the text being edited separate from the numeric value sent to the API.
function NumericInput({ value, onValueChange, ...props }: Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & { value: number | string | null; onValueChange: (value: number | null | string) => void }) {
  const [text, setText] = useState(String(value ?? ""));
  const published = useRef(value);
  useEffect(() => {
    if (!Object.is(value, published.current)) {
      published.current = value;
      setText(String(value ?? ""));
    }
  }, [value]);
  return <input {...props} type="number" value={text} onChange={event => {
    const raw = event.target.value;
    setText(raw);
    const next = raw === "" ? (props.required ? "" : null) : Number(raw);
    published.current = next;
    onValueChange(next);
  }} />;
}

export function RewardEditor({ value, onChange, disabled = false }: { value: J; onChange: (value: J) => void; disabled?: boolean }) {
  return <div className="rl-reward-fields">{Object.entries(rewardDefaults).map(([key, fallback]) => <label key={key}>
    {rewardLabels[key]} weight
    <NumericInput min={key === "capacity" || key === "energy" ? 0.000001 : 0} max="1000000" step="any" required disabled={disabled} value={value?.[key] ?? fallback} onValueChange={next => onChange({ ...rewardDefaults, ...value, [key]: next })} />
  </label>)}</div>;
}

export function RLExperimentSettings({ value, models, onChange }: { value?: J; models: J[]; onChange: (value: J) => void }) {
  const settings = { model_id: "", safety_shield: true, daily_energy_limit_kwh: null, reward: rewardDefaults, ...value };
  return <fieldset className="rl-experiment-settings">
    <legend>Learned charging controller</legend>
    <label>Trained model
      <select required value={settings.model_id} onChange={event => { const model = models.find(row => row.model_id === event.target.value); onChange(model ? modelControl(model) : { ...settings, model_id: event.target.value }); }}>
        <option value="">Select a trained policy</option>
        {settings.model_id && !models.some(model => model.model_id === settings.model_id) && <option value={settings.model_id}>{settings.model_id} · unavailable in catalog</option>}
        {models.map(model => <option key={model.model_id} value={model.model_id}>{model.name || model.model_id}</option>)}
      </select>
    </label>
    {!models.length && <p>Train a controller in the RL workspace first, then return here to select it.</p>}
    {!!models.length && <p>Selecting a model loads its training reward, shield setting, and energy budget. You can override them below for this evaluation. Training completion does not establish policy quality; check held-out charging service and violations.</p>}
    <label className="rl-check"><input type="checkbox" checked={settings.safety_shield} onChange={event => onChange({ ...settings, safety_shield: event.target.checked })} /> Apply the capacity and energy safety shield</label>
    <label>Daily total-grid energy budget (kWh; blank disables this limit)
      <NumericInput min="0.000001" step="any" value={settings.daily_energy_limit_kwh} onValueChange={next => onChange({ ...settings, daily_energy_limit_kwh: next })} />
    </label>
    <p>The budget includes baseline demand plus EV charging, excluding AC losses, from midnight to midnight. Existing baseline demand may exceed a budget even with every charger off.</p>
    <details><summary>Evaluation reward weights</summary><p>These weights change the reported score. The saved policy stays fixed; retrain in the RL workspace to learn from a different reward.</p>
      <RewardEditor value={settings.reward} onChange={reward => onChange({ ...settings, reward })} />
    </details>
  </fieldset>;
}

function RLChart({ rows, series, episode = false, selectedStep }: { rows: J[]; series: [string, string][]; episode?: boolean; selectedStep?: number }) {
  return <div className="rl-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={rows} margin={{ top: 12, right: 22, bottom: 10, left: 10 }}>
    <CartesianGrid stroke="#e4ede7" vertical={false} />
    <XAxis dataKey={episode ? "episode" : "step"} type="number" domain={["dataMin", "dataMax"]} tickFormatter={episode ? undefined : time} tick={{ fontSize: 11 }} />
    <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} width={70} />
    <Tooltip labelFormatter={value => episode ? `Episode ${value}` : time(Number(value))} formatter={(value: any, name: any) => [number(value), name]} />
    <Legend />
    {!episode && selectedStep != null && <ReferenceLine x={selectedStep} stroke="#839b8c" strokeDasharray="3 3" />}
    {series.map(([key, label], i) => <Line type="linear" key={key} dataKey={key} name={label} stroke={palette[i % palette.length]} strokeWidth={2} dot={rows.length < 2} isAnimationActive={false} connectNulls={false} />)}
  </LineChart></ResponsiveContainer></div>;
}

export function RLWorkspace({ experiments, draft, onSaved, onModels, onUseModel }: { experiments: J[]; draft: J; onSaved: (experiment: J) => void; onModels: (models: J[]) => void; onUseModel: (model: J) => void }) {
  const [trainingSection, setTrainingSection] = useState("demo");
  const cue=usePresentationCue();
  useEffect(()=>{if(cue?.view==='rl'&&['demo','campaign','legacy'].includes(cue.section||''))setTrainingSection(cue.section!);},[cue]);
  const [stored] = useState<J | null>(readTrainingDraft);
  const [config, setConfig] = useState<J>(() => ({ ...trainingDefaults, ...stored?.config, reward: { ...rewardDefaults, ...stored?.config?.reward } }));
  const configEdited = useRef(false);
  const [source, setSource] = useState<string>(stored?.source || "");
  const [models, setModels] = useState<J[]>([]);
  const [jobs, setJobs] = useState<J[]>([]);
  const [job, setJob] = useState<J | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = async (initial = false) => {
    try {
      const data = await request("/api/rl/catalog");
      setModels(data.models || []); onModels(data.models || []); setJobs(data.jobs || []);
      if (initial) {
        if (!stored && !configEdited.current) setConfig({ ...trainingDefaults, ...data.defaults, reward: { ...rewardDefaults, ...data.defaults?.reward } });
        const latest = (data.jobs || []).find((row: J) => active(row.status)) || (data.jobs || []).find((row:J)=>row.status==='completed') || data.jobs?.[0];
        if (latest) setJob(await request(`/api/rl/jobs/${encodeURIComponent(latest.job_id)}`));
      }
      setError("");
    } catch (problem: any) { setError(problem.message); }
  };
  useEffect(() => { void refresh(true); }, []);
  useEffect(() => {
    try { sessionStorage.setItem("gridlab-rl-training-draft-v1", JSON.stringify({ source, config })); } catch { /* Draft persistence is optional in restricted browsers. */ }
  }, [source, config]);
  useEffect(() => {
    if (!job?.job_id || !active(job.status)) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const latest = await request(`/api/rl/jobs/${encodeURIComponent(job.job_id)}`);
        if (disposed) return;
        setJob(latest); setError("");
        if (!active(latest.status)) { void refresh(); return; }
      } catch (problem: any) { if (!disposed) setError(`Training status unavailable: ${problem.message}. Retrying…`); }
      if (!disposed) timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 500);
    return () => { disposed = true; clearTimeout(timer); };
  }, [job?.job_id, job?.status]);
  const set = (key: string, value: any) => { configEdited.current = true; setConfig(previous => ({ ...previous, [key]: value })); };
  const saveSource = async () => {
    setBusy(true); setError("");
    try {
      const experiment = await request("/api/experiments", { method: "POST", body: JSON.stringify({ definition: draft }) });
      onSaved(experiment); setSource(experiment.experiment_id);
      setNotice(`Saved current experiment draft as ${experiment.experiment_id}. Training will use this frozen definition.`);
    } catch (problem: any) { setError(problem.message); }
    finally { setBusy(false); }
  };
  const start = async (event: React.FormEvent) => {
    event.preventDefault(); setError(""); setNotice("");
    if (!source) { setError("Select a saved experiment or save the current draft first."); return; }
    if (config.demand_scale_min > config.demand_scale_max) { setError("Minimum demand scale must not exceed the maximum."); return; }
    setBusy(true);
    try {
      const next = await request("/api/rl/train", { method: "POST", body: JSON.stringify({ experiment_id: source, config }) });
      const withConfig = { experiment_id: source, config: structuredClone(config), ...next };
      setJob(withConfig); setJobs(previous => [withConfig, ...previous.filter(row => row.job_id !== next.job_id)]);
      setNotice("Training started. Every episode generates a randomized day. You can leave this view and return to its progress.");
    } catch (problem: any) { setError(problem.message); }
    finally { setBusy(false); }
  };
  const cancel = async () => {
    if (!job) return;
    setBusy(true); setError("");
    try { const cancelled = await request(`/api/rl/jobs/${encodeURIComponent(job.job_id)}/cancel`, { method: "POST", body: "{}" }); setJob({ ...job, ...cancelled }); setNotice("Cancellation requested; waiting for the current operation to stop."); }
    catch (problem: any) { setError(problem.message); }
    finally { setBusy(false); }
  };
  const selectJob = async (id: string) => {
    if (!id) { setJob(null); return; }
    setBusy(true);
    try { setJob(await request(`/api/rl/jobs/${encodeURIComponent(id)}`)); setError(""); }
    catch (problem: any) { setError(problem.message); }
    finally { setBusy(false); }
  };
  const sourceExperiment = experiments.find(experiment => experiment.experiment_id === source);
  const history: J[] = job?.history || [];
  const last = history.at(-1);
  const running = !!job && active(job.status);
  const workerActive = running || jobs.some(row => active(row.job_id === job?.job_id ? job?.status : row.status));
  return <div className="rl-workspace">
<nav className="section-selector setup-steps" aria-label="Training sections">{[["demo", "PPO demo"], ["campaign", "PPO campaigns"], ["legacy", "Binary training"]].map(([id, label]) => <button type="button" key={id} aria-current={trainingSection === id ? 'step' : undefined} onClick={() => setTrainingSection(id)}>{label}</button>)}</nav>
    <div hidden={trainingSection !== "demo"}><PPODemo /></div>
    <div hidden={trainingSection !== "campaign"}><ContinuousRL /></div>
    <div hidden={trainingSection !== "legacy"}>
    <section className="panel rl-intro"><div><p className="eyebrow">Historical binary controller</p><h2>Learn when each charger should switch on</h2><p>A shared Bernoulli policy observes connected EVs and grid state. REINFORCE learns from randomized daily demand and charging sessions. Saved models can be tested alongside the existing strategies.</p></div><Bot size={38} /></section>
    {error && <div className="rl-error" role="alert">{error}</div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    <div className="rl-workspace-grid">
      <form className="panel rl-training-form" onSubmit={start}>
        <p className="eyebrow">1 · Define training</p><h2>Experiment & reward</h2>
        <label>Saved training experiment<select value={source} required onChange={event => setSource(event.target.value)}><option value="">Choose an immutable experiment</option>{experiments.map(experiment => <option key={experiment.experiment_id} value={experiment.experiment_id}>{experiment.definition?.name || experiment.experiment_id} · {experiment.experiment_id}</option>)}</select></label>
        <button type="button" disabled={busy} onClick={saveSource}><Save size={16} /> Save current draft and use it</button>
        <p className="rl-help">Draft: <b>{draft.name}</b>. Training uses the selected saved definition. Changes in the Experiments editor take effect after saving and selecting the new revision.</p>
        {sourceExperiment && <div className="rl-source-summary"><b>{sourceExperiment.definition?.name}</b><span>{number(sourceExperiment.definition?.fleet?.fleet_size, 0)} EVs · {sourceExperiment.definition?.demand?.month === 1 ? "January" : `Month ${sourceExperiment.definition?.demand?.month}`} · {sourceExperiment.definition?.demand?.scenario} demand</span><code>{source}</code></div>}
        <fieldset><legend>Learning configuration</legend><div className="rl-fields">
          {[["episodes", "Training episodes", 1, 1, 1000], ["seed", "Random seed", 0, 1, 4294966295], ["learning_rate", "Learning rate", 0.000001, "any", 0.1], ["gamma", "Discount factor", 0.000001, "any", 1], ["max_runtime_seconds", "Runtime budget (seconds)", 1, 1, 86400]].map(([key, label, min, step, max]) => <label key={key}>{label}<NumericInput required min={min} max={max} step={step} value={config[String(key)]} onValueChange={next => set(String(key), next)} /></label>)}
        </div></fieldset>
        <fieldset><legend>Randomized day generator</legend><div className="rl-fields">
          {[["demand_scale_min", "Minimum demand scale"], ["demand_scale_max", "Maximum demand scale"], ["shape_noise", "Demand shape noise"]].map(([key, label]) => <label key={key}>{label}<NumericInput required min={key === "shape_noise" ? 0 : 0.000001} max={key === "shape_noise" ? 0.5 : 3} step="any" value={config[key]} onValueChange={next => set(key, next)} /></label>)}
        </div><p>Demand curves and EV sessions are generated from episode seeds. Use separate experiment seeds when evaluating the saved policy.</p></fieldset>
        <fieldset><legend>Reward signal</legend><p>Delivery is rewarded. Shortfall, overload, excess energy, switching, peaks, and shield intervention are penalized. Capacity and energy penalties start at 1,000.</p><RewardEditor value={config.reward} onChange={reward => set("reward", reward)} /></fieldset>
        <fieldset><legend>Safety & energy</legend>
          <label className="rl-check"><input type="checkbox" checked={config.safety_shield} onChange={event => set("safety_shield", event.target.checked)} /> Apply safety shield during training</label>
          <label>Daily total-grid energy budget (kWh; blank disables this limit)<NumericInput min="0.000001" step="any" value={config.daily_energy_limit_kwh} onValueChange={next => set("daily_energy_limit_kwh", next)} /></label>
          <p>Midnight-to-midnight baseline + EV energy, excluding AC losses. Baseline demand alone can exceed this budget.</p>
          <p>Large penalties guide learning; they do not guarantee feasibility. Shield interventions and remaining electrical violations are recorded separately.</p>
        </fieldset>
        <p>Each start trains a fresh policy. Editing these controls changes the next job; it does not change a job already running.</p>
        <button className="primary" type="submit" disabled={busy || workerActive || !sourceExperiment}><Play size={16} /> {workerActive ? "Training in progress" : "Train a new policy"}</button>
      </form>
      <div className="rl-training-evidence">
        <section className="panel"><div className="panel-head"><div><p className="eyebrow">2 · Inspect learning</p><h2>Training progress</h2></div><button type="button" aria-label="Refresh RL catalog" disabled={busy} onClick={() => refresh()}><RefreshCw size={16} /></button></div>
          <label>Training job<select value={job?.job_id || ""} disabled={busy} onChange={event => selectJob(event.target.value)}><option value="">Select a training job</option>{jobs.map(row => <option key={row.job_id} value={row.job_id}>{row.job_id} · {row.job_id === job?.job_id ? job?.status : row.status}</option>)}</select></label>
          {job ? <><div className="rl-job-status"><b>{job.status?.replaceAll("_", " ")}</b><span>{job.completed_episodes || 0} / {job.total_episodes || config.episodes} episodes · {number(job.elapsed_seconds, 0)} s</span>{running && <button type="button" disabled={busy} onClick={cancel}><Square size={14} /> Cancel training</button>}</div><progress aria-label="Training completion" max={job.total_episodes || config.episodes} value={job.completed_episodes || 0} />
            {job.error && <div className="rl-error" role="alert">{typeof job.error === "string" ? job.error : JSON.stringify(job.error)}</div>}
            {running && job.current_episode != null && <p>Episode {job.current_episode}: interval {job.current_step || 0} / {job.total_steps || "—"} · {time(Math.max(0, (job.current_step || 1) - 1))}</p>}
            {(job.config || job.experiment_id) && <details><summary>Frozen training definition</summary><p>Source experiment: <code>{job.experiment_id || "—"}</code></p>{job.config && <><pre>{JSON.stringify(job.config, null, 2)}</pre><button type="button" onClick={() => { setConfig(structuredClone(job.config)); if (job.experiment_id) setSource(job.experiment_id); setNotice("Copied this job’s configuration into the training draft. Choose a new seed range if you want new training days."); }}>Copy settings to training draft</button></>}</details>}
            {job.model_id && <p>Saved policy: <code>{job.model_id}</code></p>}
            {!history.length && <p>{running ? "Waiting for the first complete episode…" : "This job has no completed episode evidence."}</p>}
            {!!history.length && <><h3>Episode reward</h3><RLChart rows={history} episode series={[["reward", "Reward"]]} /><div className="rl-small-metrics"><span>Latest reward<b>{number(last?.reward)}</b></span><span>Unmet energy<b>{number(last?.unmet_energy_kwh)} kWh</b></span><span>Violation intervals<b>{number(last?.violation_steps, 0)}</b></span><span>Excess energy<b>{number(last?.energy_excess_kwh)} kWh</b></span></div><h3>Charging service · kWh</h3><RLChart rows={history} episode series={[["delivered_energy_kwh", "Delivered"], ["unmet_energy_kwh", "Unmet"], ["energy_excess_kwh", "Energy excess"]]} /><h3>Constraint intervals</h3><RLChart rows={history} episode series={[["violation_steps", "Violations"], ["intervention_steps", "Shield interventions"]]} /><details><summary>Episode evidence and random seeds</summary><div className="table-wrap"><table><thead><tr>{["Episode", "Seed", "Reward", "Delivered kWh", "Unmet kWh", "Violations", "Shield intervals", "Peak kW", "Excess kWh"].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{history.map(row => <tr key={row.episode}>{["episode", "seed", "reward", "delivered_energy_kwh", "unmet_energy_kwh", "violation_steps", "intervention_steps", "peak_demand_kw", "energy_excess_kwh"].map(key => <td key={key}>{number(row[key])}</td>)}</tr>)}</tbody></table></div></details></>}
          </> : <p>Choose a saved experiment and start training. Episode rewards measure learning on randomized training days; evaluate a saved model on separate seeds before judging performance.</p>}
        </section>
        <section className="panel"><p className="eyebrow">3 · Evaluate in experiments</p><h2>Saved policies</h2><p>Select a policy to add RL to your current experiment draft. Then save the experiment and run the strategy comparison.</p>{!models.length && <p>No trained policy yet.</p>}<div className="rl-models">{models.map(model => <article key={model.model_id}><b>{model.name || model.model_id}</b><code>{model.model_id}</code><span>{model.completed_episodes} episodes · {model.created_at}</span><small>Training experiment: {model.training_experiment_id}</small><button type="button" onClick={() => onUseModel(model)}>Use in experiment <Play size={14} /></button></article>)}</div></section>
      </div>
    </div>
    </div>
  </div>;
}

const actionCount = (value: any) => Array.isArray(value) ? value.filter(Boolean).length : typeof value === "object" && value !== null ? Object.values(value).filter(Boolean).length : value;
export function RLResults({ currentCase, selectedStep }: { currentCase: J; selectedStep: number }) {
  const [inspected, setInspected] = useState<{id: string; step: number} | null>(null);
  const intervals: J[] = currentCase.intervals || [];
  const [page, setPage] = useState(0);
  const [district, setDistrict] = useState("");
  useEffect(() => { setPage(0); setDistrict(""); setInspected(null); }, [currentCase]);
  const snapshots = useMemo(() => intervals.map(interval => new Map<string, J>((interval.blocks || []).flatMap((block: J) => (block.vehicles || []).map((vehicle: J) => [String(vehicle.id), { ...vehicle, block_id: block.id }])))), [intervals]);
  const vehicles = useMemo<J[]>(() => {
    const all = new Map<string, J>();
    snapshots.forEach(snapshot => snapshot.forEach((vehicle, id) => all.set(id, vehicle)));
    return Array.from(all.entries()).map(([id, vehicle]): J => ({ ...vehicle, id })).sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));
  }, [snapshots]);
  const districts = [...new Set(vehicles.map(vehicle => vehicle.district_id).filter(Boolean))].sort();
  const filtered = vehicles.filter(vehicle => !district || vehicle.district_id === district);
  const pages = Math.max(1, Math.ceil(filtered.length / 20));
  const shownPage = Math.min(page, pages - 1);
  const rows = intervals.map((interval, step) => ({ step, ...interval.rl, requested_on: actionCount(interval.rl?.requested_on), executed_on: actionCount(interval.rl?.executed_on), ...Object.fromEntries(Object.entries(interval.rl?.components || {}).map(([key, value]) => [`component_${key}`, value])) }));
  const metrics = currentCase.metrics || {};
  const inspectedState = inspected ? snapshots[inspected.step]?.get(inspected.id) : null;
  return <div className="rl-results">
    <section className="panel"><p className="eyebrow">Learned controller evidence</p><h2>Reward, switching & constraints</h2><p>These are evaluation results from the frozen policy. The time selector highlights the same interval across all result views.</p><div className="rl-small-metrics"><span>Total reward<b>{number(metrics.rl_reward)}</b></span><span>Switches<b>{number(metrics.rl_switches, 0)}</b></span><span>Interventions<b>{number(metrics.rl_interventions, 0)}</b></span><span>Energy excess<b>{number(metrics.energy_excess_kwh)} kWh</b></span></div>
      <h3>Interval reward</h3><RLChart rows={rows} series={[["reward", "Reward"]]} selectedStep={selectedStep} />
      <h3>Reward components</h3><RLChart rows={rows} series={Object.entries(rewardLabels).map(([key, label]) => [`component_${key}`, label])} selectedStep={selectedStep} />
      <h3>Requested and executed charging</h3><RLChart rows={rows} series={[["requested_on", "Requested on"], ["executed_on", "Executed on"], ["interventions", "Interventions"], ["switches", "Switches"]]} selectedStep={selectedStep} />
    </section>
    <section className="panel"><div className="panel-head"><div><p className="eyebrow">Binary charger decisions</p><h2>Charger on / off timeline</h2></div><label>District<select value={district} onChange={event => { setDistrict(event.target.value); setPage(0); }}><option value="">All districts</option>{districts.map(id => <option key={id} value={id}>{id}</option>)}</select></label></div>
      <div className="rl-timeline-legend"><span><i className="on" /> On</span><span><i className="off" /> Paused</span><span><i className="done" /> Charged</span><span><i className="absent" /> Not connected</span></div>
      <p>Each cell is a 15-minute interval. Select or hover a cell to inspect the car. Only recorded charger states appear here.</p>
      <div className="rl-car-inspector" aria-live="polite">
        <strong>{inspected ? `${inspected.id} · ${time(inspected.step)}` : 'Select a car and an interval'}</strong>
        {inspected && <div className="rl-small-metrics">
          <span>Applied charging power<b>{inspectedState ? `${number(inspectedState.power_kw)} kW` : 'Not connected'}</b></span>
          <span>Remaining battery demand<b>{inspectedState ? `${number(inspectedState.remaining_kwh)} kWh` : '—'}</b></span>
          <span>Recorded state<b>{inspectedState?.status || 'Not connected'}</b></span>
          <span>Demand block<b>{inspectedState?.block_id || '—'}</b></span>
        </div>}
      </div>
      <div className="rl-timeline-scroll"><table className="rl-timeline"><thead><tr><th>Charger / EV</th>{intervals.map((_, step) => <th key={step} className={step === selectedStep ? "selected" : ""}><span>{step % 4 === 0 ? time(step) : ""}</span></th>)}</tr></thead><tbody>{filtered.slice(shownPage * 20, shownPage * 20 + 20).map(vehicle => <tr key={vehicle.id}><th title={`${vehicle.district_id} · ${vehicle.block_id}`}>{vehicle.id}</th>{snapshots.map((snapshot, step) => { const state = snapshot.get(vehicle.id); const mode = !state ? "absent" : state.power_kw > 1e-9 ? "on" : state.status === "completed" ? "done" : "off"; const label = `${vehicle.id} · ${time(step)} · ${state ? `${mode === "on" ? "On" : mode === "done" ? "Charged" : "Paused"} · ${number(state.power_kw)} kW · ${number(state.remaining_kwh)} kWh remaining` : "Not connected"}`; return <td key={step} className={`${mode} ${step === selectedStep ? "selected" : ""}`} title={label} aria-label={label} tabIndex={step === selectedStep ? 0 : -1} onMouseEnter={() => setInspected({id: vehicle.id, step})} onFocus={() => setInspected({id: vehicle.id, step})} onClick={() => setInspected({id: vehicle.id, step})} />; })}</tr>)}</tbody></table></div>
      {!filtered.length && <p>No recorded charger states for this selection.</p>}
      <div className="rl-pagination"><button disabled={shownPage === 0} onClick={() => setPage(shownPage - 1)}>Previous</button><span>{filtered.length} chargers · page {shownPage + 1} / {pages}</span><button disabled={shownPage >= pages - 1} onClick={() => setPage(shownPage + 1)}>Next</button></div>
    </section>
  </div>;
}
