import { useEffect, useState } from 'react';
import './strategies.css';
type J = Record<string, any>;

export function openStrategyChat(message: string) {
  window.dispatchEvent(new CustomEvent('strategy-chat', { detail: message }));
}

const stages = ['PROPOSE', 'SPECIFY', 'BUILD', 'COMPARE', 'CHALLENGE', 'REVISE'];
function template(stage: string, record: string, scenario: string) {
  const parent = record || '<select a saved record>';
  const experiment = scenario || '<select a saved scenario>';
  const templates: Record<string, string> = {
    PROPOSE: 'name: deadline_headroom\nidea: Allocate available grid capacity according to charging urgency.\nobjective: Meet departure energy requests within network limits.\nresearch: adaptation',
    SPECIFY: `based_on: ${parent}\ninformation: [connected sessions, current baseline, known grid capacity]\nconstraints: [charger limits, energy requirements, network limits]\nalgorithm: Describe the allocation rule and decision interval.\nfallback: Describe behavior if inputs or the solver fail.\nreferences: []`,
    BUILD: `based_on: ${parent}`,
    COMPARE: `scenario: ${experiment}\ncandidates: [capacity_aware, least_laxity_first, valley_filling, mpc, voltage_responsive]\nseeds: [11, 12]\nmax_cases: 10\nmax_runtime_seconds: 300`,
    CHALLENGE: `scenario: ${experiment}\ncandidates: [capacity_aware, mpc]\nseeds: [11]\nmax_cases: 4\nmax_runtime_seconds: 300\nvariations:\n  - fleet_sizes: [100, 1000]`,
    REVISE: `based_on: ${parent}\nidea: Describe the revision and the counterexample it addresses.`,
  };
  return `STRATEGY ${stage}\n${templates[stage]}`;
}

export function StrategyOptionsEditor({ value, onChange }: { value: J; onChange: (value: J) => void }) {
  return <fieldset><legend>Controller planning</legend>
    <p>Forecasts use current measurements or observed history. Future arrivals are not revealed.</p>
    <div className="strategy-options">
      <label>Baseline forecast<select aria-label="Baseline forecast" value={value?.forecast || 'persistence'} onChange={e => onChange({ ...value, forecast: e.target.value })}>
        <option value="persistence">Current baseline persists</option><option value="previous_day">Previous day, with persistence fallback</option>
      </select></label>
      <label>Planning horizon (15-minute steps)<input type="number" min="1" max="192" value={value?.horizon_steps ?? 96} onChange={e => onChange({ ...value, horizon_steps: +e.target.value })} /></label>
      <label>MPC solve limit (seconds per stage)<input type="number" min="0.1" max="30" step="0.1" value={value?.solver_seconds ?? 3} onChange={e => onChange({ ...value, solver_seconds: +e.target.value })} /></label>
    </div>
    <small>MPC and valley filling use these planning settings. Continuous controllers and learned on/off policies have different action constraints.</small>
  </fieldset>;
}

export function StrategiesWorkspace({ experiments, onUse, onPrepared }: { experiments: J[]; onUse: (id: string) => void; onPrepared: () => void }) {
  const [catalog, setCatalog] = useState<J>({});
  const [record, setRecord] = useState('');
  const [scenario, setScenario] = useState('');
  const [command, setCommand] = useState(template('PROPOSE', '', ''));
  const [output, setOutput] = useState<J | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const request = async (path: string, options?: RequestInit) => {
    const response = await fetch(path, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  };
  const refresh = async () => {
    try { setCatalog(await request('/api/strategies')); } catch (e: any) { setError(e.message); }
  };
  useEffect(() => { refresh(); }, []);
  const submit = async () => {
    setBusy(true); setError('');
    try {
      const result = await request('/api/strategies/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command }) });
      setOutput(result);
      if (result.record_id) setRecord(result.record_id);
      await refresh();
      if (result.experiments) onPrepared();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  return <div className="strategy-workspace">
    <section className="panel"><p className="eyebrow">Charging controller library</p><h2>One scenario, different charging decisions</h2>
      <p>Choose a controller for your experiment or develop a research-backed idea. Train learned policies in the RL workspace, then compare them here using the same scenario.</p>
      <div className="strategy-grid">{(catalog.strategies || []).map((strategy: J) => <article key={strategy.id} className="strategy-card">
        <span className="strategy-family">{strategy.family.replaceAll('_', ' ')}</span><h3>{strategy.label}</h3><p>{strategy.description}</p>
        <small>{strategy.action_space === 'binary_on_off' ? 'On/off decisions · trained model required' : 'Charging power in kW'}</small>
        <details><summary>Inputs and limitations</summary><p>{strategy.observations}. Forecast: {strategy.forecast}.</p><p>{strategy.limitation}</p>
          {strategy.research_url && <a href={strategy.research_url} target="_blank" rel="noreferrer">Read supporting research</a>}</details>
        <button className="ghost" onClick={() => onUse(strategy.id)}>Use in experiment</button>
      </article>)}</div>
    </section>
    <section className="panel"><p className="eyebrow">Strategy development</p><h2>From an idea to a tested controller</h2>
      <p>Save a proposal, complete its specification, build it with Codex, then prepare a comparison or challenge. Records are versioned; earlier evidence stays available.</p>
      <div className="strategy-options">
        <label>Saved strategy record<select value={record} onChange={e => setRecord(e.target.value)}><option value="">Choose a record</option>{(catalog.records || []).map((r: J) => <option key={r.record_id} value={r.record_id}>{r.name} · {r.stage} · {r.record_id.slice(-6)}</option>)}</select></label>
        <label>Saved comparison scenario<select value={scenario} onChange={e => setScenario(e.target.value)}><option value="">Choose a scenario</option>{experiments.map(e => <option key={e.experiment_id} value={e.experiment_id}>{e.definition?.name || e.experiment_id}</option>)}</select></label>
      </div>
      <div className="strategy-stages">{stages.map(stage => <button key={stage} className="ghost" onClick={() => setCommand(template(stage, record, scenario))}>{stage[0]+stage.slice(1).toLowerCase()}</button>)}</div>
      <label className="strategy-command">Standard command<textarea aria-label="Strategy workflow command" rows={11} value={command} onChange={e => setCommand(e.target.value)} spellCheck={false} /></label>
      <p className="strategy-help">Save / prepare validates the command. Build prepares a coding handoff; the assistant performs implementation. Compare and Challenge prepare experiments without starting runs.</p>
      <div className="strategy-stages"><button className="primary" disabled={busy || !command.trim()} onClick={submit}>{busy ? 'Validating…' : 'Save / prepare'}</button>
        <button className="ghost" onClick={() => openStrategyChat(command)}>Continue with assistant</button>
        {record && <button className="ghost" onClick={async () => { try { setOutput(await request(`/api/strategies/${record}`)); setError(''); } catch (e: any) { setError(e.message); } }}>Read selected record</button>}</div>
      {error && <p role="alert" className="strategy-error">{error}</p>}
      {output && <div className="strategy-output"><strong>{String(output.status).replaceAll('_',' ')}</strong>{output.record_id && <p>{output.record_id}</p>}
        {output.coding_prompt && <><p>The specification is ready for implementation. Send it to the assistant to build and test it.</p><button className="primary" onClick={() => openStrategyChat(`STRATEGY BUILD\nbased_on: ${output.parent}`)}>Build with assistant</button></>}
        {output.experiments && <p>Prepared {output.total_cases} cases. Open Experiments to start the saved comparisons.</p>}
        <details><summary>Record and evidence</summary><pre>{JSON.stringify(output, null, 2)}</pre></details>
      </div>}
    </section>
  </div>;
}
