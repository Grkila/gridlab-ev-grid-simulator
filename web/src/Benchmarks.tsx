import { useEffect, useState } from 'react';
import { BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './benchmarks.css';
import { visibleControllers } from './visibleControllers';

type J = Record<string, any>;
const request = async (path: string, payload?: J) => {
  const response = await fetch(path, payload ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : undefined);
  const body = await response.json();
  if (!response.ok) throw Error(body.error || `HTTP ${response.status}`);
  return visibleControllers(body);
};
const number = (value: any, digits = 1) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
const active = (status: string) => ['starting', 'running'].includes(status);
const statusLabel = (status: string) => ({ ceiling_reached: 'Search ceiling reached', bounded: 'Largest tested pass', baseline_limited: 'Grid fails with 0 cars', no_common_fleet: 'No shared pass', budget_exceeded: 'Time limit reached', passed: 'Pass', failed: 'Fail', incomplete: 'Unknown / incomplete' }[status] || status || 'Not run');
const colors = ['#00875a', '#287ca1', '#8b5fa7', '#b06d21', '#527338', '#a85569', '#496cbb', '#747474', '#21a8a0'];

function download(data: J) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = `benchmark-${data.job.job_id}.json`; link.click(); URL.revokeObjectURL(url);
}

export function BenchmarksWorkspace() {
  const [catalog, setCatalog] = useState<J>({}), [models, setModels] = useState<J[]>([]);
  const [suiteId, setSuiteId] = useState(''), [jobId, setJobId] = useState('');
  const [draft, setDraft] = useState<J>({ name: 'Novi Sad · doubling test', standard_fleet: 500, max_fleet: 32768, district: '', operating_mode: 'regulated', search_mode: 'doubling', until_failure: true, aggregate_ev_nodes: true });
  const [seeds, setSeeds] = useState('41001, 41002, 41003'), [selected, setSelected] = useState<string[]>([]);
  const [modelId, setModelId] = useState(''), [runtime, setRuntime] = useState(3600), [caseRuntime, setCaseRuntime] = useState(120);
  const [data, setData] = useState<J | null>(null), [cell, setCell] = useState<J | null>(null), [comparison, setComparison] = useState<J | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [chartTest, setChartTest] = useState('city_max');
  const refresh = async () => {
    const [c, r] = await Promise.all([request('/api/benchmarks'), request('/api/rl/catalog')]);
    setCatalog(c); setModels(r.models || []); return c;
  };
  useEffect(() => { let mounted = true; refresh().then(c => {
    if (!mounted) return;
    setSelected(c.strategies.filter((s: J) => !['rl','mpc'].includes(s.id)).map((s: J) => s.id));
    if (c.jobs.length) { const preferred = c.jobs.find((j: J) => active(j.status)) || c.jobs.find((j: J) => j.status === 'completed') || c.jobs[0]; setJobId(preferred.job_id); setSuiteId(preferred.suite_id); }
    else if (c.suites.length) setSuiteId(c.suites[c.suites.length - 1].suite_id);
  }).catch(e => setError(e.message)); return () => { mounted = false; }; }, []);
  useEffect(() => {
    if (!jobId) { setData(null); return; }
    let cancelled = false; let timer: ReturnType<typeof setTimeout>;
    setData(null); setCell(null);
    const poll = async () => {
      try {
        const result = await request(`/api/benchmarks/jobs/${jobId}`);
        if (cancelled) return;
        setData(result);
        if (active(result.job.status)) timer = setTimeout(poll, 2000);
      } catch (e: any) { if (!cancelled) setError(e.message); }
    };
    poll(); return () => { cancelled = true; clearTimeout(timer); };
  }, [jobId]);
  const perform = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); try { await action(); } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  const saveSuite = () => perform(async () => {
    const values = seeds.split(',').map(s => s.trim());
    if (values.some(s => !/^\d+$/.test(s))) throw Error('Enter comma-separated integer seeds.');
    const suite = await request('/api/benchmarks/suites', { definition: { ...draft, district: draft.district || null, seeds: values.map(Number) } });
    setSuiteId(suite.suite_id); setComparison(null); await refresh();
  });
  const start = () => perform(async () => {
    const job = await request('/api/benchmarks/jobs', { suite_id: suiteId, config: { strategies: selected, model_id: modelId || null, max_runtime_seconds: runtime, case_runtime_seconds: caseRuntime } });
    setJobId(job.job_id); setComparison(null); await refresh();
  });
  const suite = (catalog.suites || []).find((s: J) => s.suite_id === suiteId);
  const evaluatedSuite = (catalog.suites || []).find((s: J) => s.suite_id === data?.job.suite_id);
  const rows: J[] = data?.rows || [], algorithms: string[] = data?.job.strategies || [];
  const label = (id: string) => (catalog.strategies || []).find((s: J) => s.id === id)?.label || id;
  const chosen = cell ? rows.find(r => r.test_id === cell.test_id && r.strategy === cell.strategy) : null;
  const chartRows = rows.filter(r => r.test_id === chartTest).map(r => ({ algorithm: label(r.strategy), cars: r.fleet_size, status: statusLabel(r.status) }));
  const running = active(data?.job.status);

  return <div className="benchmark-workspace">
    <section className="panel benchmark-intro">
      <div><p className="eyebrow">One protocol · ten tests</p><h2>Compare service, stress and spare capacity</h2>
        <p>Every algorithm gets identical vehicles, demand and seeds. Passing means all requested energy delivered by departure with no electrical violations.</p></div>
      <div className="benchmark-badge">10<span>standard fixtures</span></div>
    </section>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="benchmark-setup">
      <section className="panel">
        <h3>1. Freeze the benchmark</h3>
        <label>Saved benchmark<select aria-label="Saved benchmark" value={suiteId} onChange={e => { setSuiteId(e.target.value); setComparison(null); }}>
          <option value="">Create a benchmark below</option>{(catalog.suites || []).map((s: J) => <option key={s.suite_id} value={s.suite_id}>{s.config.name} · {s.config.standard_fleet} reference / {s.config.until_failure ? "until failure" : `${s.config.max_fleet} ceiling`} cars · {s.suite_id.slice(-6)}</option>)}
        </select></label>
        {suite && <div className="benchmark-frozen"><strong>Frozen: {suite.config.name}</strong><p>{suite.config.seeds.length} seed(s) · reference {number(suite.config.standard_fleet, 0)} cars · {suite.config.until_failure ? "no car-count ceiling" : `ceiling ${number(suite.config.max_fleet, 0)}`} · district {suite.config.district}</p>
          <small>Search ladder: {suite.config.until_failure ? '0-car control → 2 → 4 → 8 → 16 → … until failure (no car-count ceiling)' : `${suite.ladder.join(' → ')} cars`}</small></div>}
        {suite?.config.operating_mode === 'regulated' && <p>Voltage-regulated grid · source voltage 1.04 pu · baseline demand shifted to a 220 MW peak, preserving daily energy.</p>}
        {suite?.config.aggregate_ev_nodes && <p>EV control: adjustable load at each node, grouped by matching arrival, departure, charger power and energy need. Continuous power is shared equally within each group.</p>}
        <details open={!suiteId}><summary>Create a new standard benchmark</summary>
          <div className="benchmark-fields">
            <label><input type="checkbox" checked={draft.aggregate_ev_nodes} onChange={e=>setDraft({...draft,aggregate_ev_nodes:e.target.checked})}/>Aggregate EV control at each node</label>
            <label>Name<input aria-label="Benchmark name" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
            <label>Grid operation<select aria-label="Benchmark grid operation" value={draft.operating_mode} onChange={e => setDraft({...draft,operating_mode:e.target.value})}><option value="regulated">Voltage-regulated grid</option><option value="as_supplied">Original operating assumptions</option></select></label>
            <label>Reference cars<input aria-label="Reference cars" type="number" min={1} max={50000} value={draft.standard_fleet} onChange={e => setDraft({ ...draft, standard_fleet: +e.target.value })} /></label>
            <label>Capacity search<select aria-label="Capacity search" value={draft.search_mode} onChange={e => setDraft({...draft,search_mode:e.target.value,until_failure:e.target.value==='doubling'})}><option value="doubling">Double from 2 cars until first failure</option><option value="refined">Reference ladder with one-car refinement</option></select></label>
            {!draft.until_failure && <label>Search ceiling (cars)<input aria-label="Search ceiling (cars)" type="number" min={1} max={50000} value={draft.max_fleet} onChange={e => setDraft({ ...draft, max_fleet: +e.target.value })} /></label>}
            <label>Evaluation seeds<input aria-label="Evaluation seeds" value={seeds} onChange={e => setSeeds(e.target.value)} /></label>
            <label>Concentrated district<select aria-label="Concentrated district" value={draft.district} onChange={e => setDraft({ ...draft, district: e.target.value })}><option value="">Busiest by baseline loading</option>{(catalog.districts || []).map((d: J) => <option key={d.id} value={d.id}>{d.id}</option>)}</select></label>
          </div>
          <button disabled={busy} onClick={saveSuite}>Freeze 10-test benchmark</button>
        </details>
      </section>
      <section className="panel">
        <h3>2. Choose algorithms</h3>
        <div className="benchmark-algorithms">{(catalog.strategies || []).map((s: J) => <label key={s.id} title={s.limitation}>
          <input type="checkbox" checked={selected.includes(s.id)} onChange={e => setSelected(e.target.checked ? [...selected, s.id] : selected.filter(id => id !== s.id))} />{s.label}
        </label>)}</div>
        <p className="muted">New registered algorithms appear here automatically. Repeat this saved benchmark to compare their results.</p>
        {selected.includes('rl') && <label>Frozen RL policy<select aria-label="Benchmark RL model" value={modelId} onChange={e => setModelId(e.target.value)}><option value="">Select a trained model</option>{models.map(m => <option key={m.model_id} value={m.model_id}>{m.name || m.model_id} · {m.completed_episodes} episodes</option>)}</select></label>}
        <div className="benchmark-fields">
          <label>Total time limit (seconds)<input aria-label="Benchmark time limit" type="number" min={1} max={43200} value={runtime} onChange={e => setRuntime(+e.target.value)} /></label>
          <label>Per-case limit (seconds)<input aria-label="Benchmark case limit" type="number" min={1} max={3600} value={caseRuntime} onChange={e => setCaseRuntime(+e.target.value)} /></label>
        </div>
        <button className="primary" disabled={busy || running || !suiteId || !selected.length || (selected.includes('rl') && !modelId)} onClick={start}>Run benchmark</button>
        <small>Each case covers 33 hours at 15-minute resolution. Large fleets and multiple seeds can take substantial time; unfinished cases remain unknown.</small>
      </section>
    </div>
    <details className="panel benchmark-fixtures"><summary>The ten standard tests</summary><ol>{(catalog.tests || []).map((t: J) => <li key={t.id}><strong>{t.title}</strong><span>{t.description}</span></li>)}</ol>
      <p>Overnight residential visits: 14 kWh per EV, 7.4 kW chargers, 90% efficiency, departures at 09:00. Normal day is June; worst winter uses January +20%. New suites treat supplied consumption as grid input including network losses. Historical suites keep their original measurement boundary.</p></details>
    <section className="panel">
      <div className="benchmark-toolbar"><h3>Benchmark results</h3><label>Saved run<select aria-label="Saved benchmark run" value={jobId} onChange={e => setJobId(e.target.value)}><option value="">Select a run</option>{(catalog.jobs || []).map((j: J) => <option key={j.job_id} value={j.job_id}>{j.created_at.slice(0, 16).replace('T', ' ')} · {j.strategies.length} algorithms · {j.job_id.slice(-6)}</option>)}</select></label>
        <button onClick={() => perform(async () => { await refresh(); })}>Refresh benchmarks</button>
        {data && <button onClick={() => download(data)}>Export results JSON</button>}
      </div>
      {!data && <p>{jobId ? 'Loading saved results…' : 'Run the benchmark to populate measured results. No scores are estimated in advance.'}</p>}
      {data && <>
        <div className="benchmark-run-state" aria-live="polite"><strong>{statusLabel(data.job.status)}</strong><span>{data.job.completed_rows} / {data.job.total_rows} cells · {number(data.job.elapsed_seconds, 0)} seconds</span>
          {running && <><span>{data.job.current_test} · {label(data.job.current_strategy || '')} · {number(data.job.current_fleet, 0)} cars · interval {data.job.current_step || 0}/132</span><button disabled={busy} onClick={() => perform(async () => { await request(`/api/benchmarks/jobs/${jobId}/cancel`, {}); })}>Cancel benchmark</button></>}
        </div>
        <progress aria-label="Benchmark progress" max={data.job.total_rows} value={data.job.completed_rows} />
        {data.job.error && <p role="alert">{data.job.error}</p>}
        <p className="muted">{evaluatedSuite?.config.name} · fixture {data.job.suite_id} · implementation {data.job.implementation_id}. Status “completed” means evaluation finished, not that every algorithm passed.</p>
        {evaluatedSuite?.config.operating_mode === 'regulated' && <p className="muted">Operating assumptions: 1.04 pu source voltage and energy-preserving baseline peak shifting to 220 MW. Grid limits remain 0.95–1.05 pu and 100% loading.</p>}
        {evaluatedSuite?.config.max_fleet <= 10 && <p role="note">This run searched only up to {number(evaluatedSuite.config.max_fleet, 0)} cars. It is a small verification run and cannot establish maximum car capacity.</p>}
        <p className="muted">Each car requests 14 kWh of energy and charges at up to 7.4 kW of power. Ten simultaneous chargers draw at most 74 kW. A zero-car grid failure comes from baseline demand or network assumptions.</p>
        <div className="benchmark-metrics">
          <div><span>Shared passing fleet</span><strong>{number(data.common_fleet, 0)} <small>cars</small></strong><small>{data.common_fleet == null ? 'No verified common fleet yet' : 'All selected algorithms, every seed'}</small></div>
          <div><span>Fixed tests passed</span><strong>{rows.filter(r => r.kind === 'fixed' && r.status === 'passed').length} <small>/ {algorithms.length * 5}</small></strong><small>Full energy + grid compliance</small></div>
          <div><span>Fleet search</span><strong>{evaluatedSuite?.config.until_failure ? 'Until failure' : `${number(evaluatedSuite?.config.max_fleet, 0)} cars`}</strong><small>{evaluatedSuite?.config.until_failure ? 'No car-count ceiling; unfinished trials remain unknown' : 'Reaching the ceiling is a lower bound, not maximum capacity'}</small></div>
        </div>
        <div className="table-wrap benchmark-matrix"><table><caption>Ten-test comparison — select a cell for metrics and trial history</caption><thead><tr><th scope="col">Standard test</th>{algorithms.map(s => <th scope="col" key={s}>{label(s)}</th>)}</tr></thead><tbody>
          {(catalog.tests || []).map((t: J) => <tr key={t.id}><th scope="row">{t.title}</th>{algorithms.map(s => {
            const row = rows.find(r => r.test_id === t.id && r.strategy === s);
            return <td key={s}>{row ? <button className={`benchmark-cell ${row.status}`} onClick={() => setCell(row)} aria-label={`${t.title}: ${label(s)}: ${statusLabel(row.status)}`}>
              <strong>{row.status === 'baseline_limited' ? '0-car baseline fails' : row.kind === 'capacity' ? row.fleet_size == null ? 'No verified passing count' : `${number(row.fleet_size, 0)} cars passed` : statusLabel(row.status)}</strong>
              <small>{row.kind === 'capacity' ? row.status === 'ceiling_reached' ? 'Maximum not yet found · search ceiling reached' : statusLabel(row.status) : row.fleet_size == null ? 'See trial history' : `${number(row.fleet_size, 0)} cars · ${number(row.metrics.unmet_energy_kwh, 3)} kWh unmet`}</small>
              {row.baseline?.metrics && <small>0-car baseline: {number(row.baseline.metrics.min_voltage_pu, 4)} pu · {number(row.baseline.metrics.max_line_loading_percent, 1)}% line loading</small>}
              {row.metrics?.min_stage_headroom_kw != null && <small>{row.metrics.min_stage_headroom_kw >= 0 ? 'Stage capacity margin' : 'Stage capacity overload'}: {number(Math.abs(row.metrics.min_stage_headroom_kw) / 1000, 2)} MW</small>}
              {row.status === 'failed' && row.reasons?.length > 0 && <small>{row.reasons.join('; ')}</small>}
              {row.kind === 'fixed' && row.baseline?.status === 'failed' && <small>Also fails with 0 cars</small>}
              {row.next_failed_fleet != null && <small>{number(row.next_failed_fleet, 0)} cars: tested fail</small>}
              {row.first_failed_doubling != null && <small>First failed doubling: {number(row.first_failed_doubling, 0)} cars (2^{Math.log2(row.first_failed_doubling)})</small>}
            </button> : <span className="muted">Not run</span>}</td>;
          })}</tr>)}
        </tbody></table></div>
        <div className="benchmark-toolbar"><h3>Cars served within all limits</h3><label>Capacity chart<select aria-label="Capacity chart test" value={chartTest} onChange={e => setChartTest(e.target.value)}>{(catalog.tests || []).filter((t: J) => t.kind === 'capacity').map((t: J) => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label></div>
        {chartRows.length > 0 ? <div className="benchmark-chart"><ResponsiveContainer width="100%" height={270}><BarChart data={chartRows} margin={{ bottom: 35 }}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="algorithm" tick={{ fontSize: 11 }} interval={0} /><YAxis allowDecimals={false} /><Tooltip formatter={(v: any) => [number(v, 0), 'Largest passing tested fleet']} /><Legend /><Bar dataKey="cars" name="Largest passing tested fleet" fill={colors[0]} /></BarChart></ResponsiveContainer></div> : <p>Capacity trials have not finished.</p>}
        <p className="muted">Bars are tested passing counts. Read the matrix status: ceiling reached, incomplete and baseline limited are not exact capacity estimates. Missing values are not zero.</p>
      </>}
    </section>
    {chosen && <section className="panel benchmark-detail"><h3>{label(chosen.strategy)} · {(catalog.tests || []).find((t: J) => t.id === chosen.test_id)?.title}</h3><p>{statusLabel(chosen.status)} · {chosen.note || chosen.reasons?.join('; ')}</p>
      {chosen.baseline && <p>Zero-car control: {statusLabel(chosen.baseline.status)}. Minimum voltage {number(chosen.baseline.metrics.min_voltage_pu, 4)} pu; line loading {number(chosen.baseline.metrics.max_line_loading_percent, 2)}%; transformer loading {number(chosen.baseline.metrics.max_transformer_loading_percent, 2)}%. {chosen.baseline.reasons?.join('; ')}</p>}
      <div className="benchmark-metrics">{[
        ['Cars', chosen.fleet_size, ''], ['Delivered', chosen.metrics.delivered_energy_kwh, 'kWh'], ['Unmet', chosen.metrics.unmet_energy_kwh, 'kWh'],
        ['City peak', chosen.metrics.peak_demand_kw == null ? null : chosen.metrics.peak_demand_kw / 1000, 'MW'], ['Minimum voltage', chosen.metrics.min_voltage_pu, 'pu'],
        ['Minimum stage headroom', chosen.metrics.min_stage_headroom_kw == null ? null : chosen.metrics.min_stage_headroom_kw / 1000, 'MW'],
        ['Spare stage capacity', chosen.metrics.spare_stage_percent, '%'], ['Spare district capacity', chosen.metrics.spare_district_percent, '%'],
        ['Max line loading', chosen.metrics.max_line_loading_percent, '%'], ['Max transformer loading', chosen.metrics.max_transformer_loading_percent, '%'],
        ['Violation intervals', chosen.metrics.violation_intervals, ''], ['Fallback intervals', chosen.metrics.fallback_intervals, ''],
        ['Safety interventions', chosen.metrics.safety_intervals, ''], ['Optimizer iteration caps', chosen.metrics.optimizer_limit_intervals, ''],
        ['Case runtime', chosen.metrics.runtime_seconds, 's'], ['Extra tested cars vs shared fleet', chosen.additional_cars_vs_common, ''],
        ['Grid input peak including losses', chosen.metrics.supply_peak_kw == null ? null : chosen.metrics.supply_peak_kw / 1000, 'MW'],
        ['Loss reconciliation error', chosen.metrics.baseline_loss_reconciliation_max_error_kw, 'kW'],
        ['EV grid input including incremental losses', chosen.metrics.incremental_ev_supply_energy_kwh, 'kWh'],
      ].map(([title, value, unit]) => <div key={title}><span>{title}</span><strong>{number(value, unit === 'pu' ? 4 : 2)} <small>{unit}</small></strong></div>)}</div>
      <p>Metrics show the worst seed: lowest delivery/headroom/voltage and highest unmet energy/peak/loading/runtime. Headroom is the minimum across intervals and modeled capacity stages; it is not a claim of extra physical parking or charger slots.</p>
      {chosen.attempts && <div className="table-wrap"><table><caption>Every tested fleet, including failures and unknowns</caption><thead><tr><th>Cars</th><th>Status</th><th>Delivered kWh</th><th>Unmet kWh</th><th>Peak MW</th><th>Spare capacity %</th><th>Seed results</th></tr></thead><tbody>{chosen.attempts.map((a: J) => <tr key={a.fleet_size}><td>{number(a.fleet_size, 0)}</td><td title={a.reasons?.join('; ')}>{statusLabel(a.status)}</td><td>{number(a.metrics.delivered_energy_kwh, 3)}</td><td>{number(a.metrics.unmet_energy_kwh, 3)}</td><td>{number(a.metrics.peak_demand_kw == null ? null : a.metrics.peak_demand_kw / 1000, 3)}</td><td>{number(a.metrics.spare_stage_percent)}</td><td>{a.trials?.map((t: J) => `${t.seed}: ${t.status}`).join(' · ')}</td></tr>)}</tbody></table></div>}
    </section>}
    <section className="panel"><h3>Compare new algorithms with saved implementations</h3><p>Run a new registered algorithm on the same frozen benchmark, then load the saved comparison. Implementation versions and settings remain separate; changing the fixture creates a different benchmark.</p>
      <button disabled={!suiteId || busy} onClick={() => perform(async () => setComparison(await request(`/api/benchmarks/suites/${suiteId}/compare`)))}>Compare saved implementations</button>
      {comparison && <><p>{comparison.note}</p><div className="table-wrap"><table><caption>Completed runs on {comparison.suite_id}; shared-fleet test excluded because its cohort changes</caption><thead><tr><th>Algorithm</th><th>Implementation / settings</th><th>Test</th><th>Status</th><th>Cars</th><th>Unmet kWh</th></tr></thead><tbody>{comparison.rows.map((r: J) => <tr key={`${r.strategy}-${r.candidate_id}-${r.test_id}`}><td>{label(r.strategy)}</td><td>{r.implementation_id} / {r.candidate_id}</td><td>{r.test_id}</td><td>{statusLabel(r.status)}</td><td>{number(r.fleet_size, 0)}</td><td>{number(r.metrics.unmet_energy_kwh, 3)}</td></tr>)}</tbody></table></div>{!comparison.rows.length && <p>No completed implementations yet.</p>}</>}
    </section>
    <p className="benchmark-scope">Synthetic balanced MV planning model. Central safety overlays differ between algorithms and their interventions are reported. RL uses its frozen policy with the shield enabled and no daily energy budget. These tests do not certify real-city hosting capacity.</p>
  </div>;
}
