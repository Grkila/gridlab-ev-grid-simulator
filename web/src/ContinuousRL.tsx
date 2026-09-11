import { useEffect, useState } from 'react';
type J = Record<string, any>;
async function api(path: string, body?: J) {
  const response = await fetch('/api/' + path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : JSON.stringify(data.error || data));
  return data;
}
export function ContinuousRL() {
  const [jobs, setJobs] = useState<J[]>([]), [campaigns, setCampaigns] = useState<J[]>([]);
  const [benchmark, setBenchmark] = useState(''), [hours, setHours] = useState(10);
  const [selected, setSelected] = useState(''), [result, setResult] = useState<J | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    let disposed = false;
    const refresh = async () => { try {
      const [b, c] = await Promise.all([api('benchmarks'), api('continuous-rl/catalog')]);
      if (!disposed) { setJobs(b.jobs || []); setCampaigns(c.campaigns || []); setSelected(previous=>previous||c.campaigns?.find((item:J)=>item.status==='completed')?.campaign_id||c.campaigns?.[0]?.campaign_id||''); }
    } catch (e) { if (!disposed) setError(String(e)); } };
    void refresh(); const timer = setInterval(refresh, 10000);
    return () => { disposed = true; clearInterval(timer); };
  }, []);
  useEffect(() => {
    let disposed = false;
    setResult(null);
    if (!selected) return;
    const refresh = async () => { try { const r = await api(`continuous-rl/campaigns/${selected}/results`); if (!disposed) setResult(r); } catch (e) { if (!disposed) setError(String(e)); } };
    void refresh(); const timer = setInterval(refresh, 5000);
    return () => { disposed = true; clearInterval(timer); };
  }, [selected]);
  async function act(action: string) {
    setBusy(true); setError('');
    try {
      const r = action === 'prepare' ? await api('continuous-rl/campaigns', { benchmark_job_id: benchmark, config: { budget_hours: hours } }) : await api(`continuous-rl/campaigns/${selected}/${action}`, {});
      if (action === 'prepare') { setSelected(r.campaign_id); setCampaigns(old => [...old, r]); }
      else setResult(await api(`continuous-rl/campaigns/${selected}/results`));
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const state = result?.campaign, running = ['queued','starting','running'].includes(state?.status);
  return <section className="panel rl-training-form" aria-label="Continuous benchmark RL">
    <p className="eyebrow">Continuous node PPO</p><h2>Learn against a frozen benchmark</h2>
    <p>Campaigns replay the original benchmark before training, screen three learning rates, and evaluate three independent training seeds on held-out days. The objective is to outperform all seven benchmark policies on matched held-out days. Training includes fleets around and above their strongest tested bounds. Complete charging and grid limits take priority over peak reduction.</p>
    {error && <p role="alert" className="rl-error">{error}</p>}
    <div className="rl-fields"><label>Source benchmark<select value={benchmark} onChange={e => setBenchmark(e.target.value)}><option value="">Choose benchmark evidence</option>{jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.job_id} · {j.status} · {j.completed_rows}/{j.total_rows} rows</option>)}</select></label>
    <label>Campaign hours (maximum 12)<input type="number" min="1" max="12" step="1" value={hours} onChange={e => setHours(Number(e.target.value))} /></label></div>
    <button disabled={busy || !benchmark || !Number.isFinite(hours) || hours < 1 || hours > 12} onClick={() => void act('prepare')}>Freeze campaign</button>
    <label>Saved campaign<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Choose campaign</option>{campaigns.map(c => <option key={c.campaign_id} value={c.campaign_id}>{c.campaign_id} · {c.status}</option>)}</select></label>
    {state && <><p role="status"><b>{state.status}</b> · {state.phase} · {Math.round((state.elapsed_seconds || 0)/60)} minutes elapsed</p>
    {state.error && <p className="rl-error">{state.error}</p>}
    <div className="rl-fields"><button disabled={busy || state.status !== 'prepared'} onClick={() => void act('start')}>Start campaign</button><button disabled={busy || running || ['prepared','completed'].includes(state.status)} onClick={() => void act('resume')}>Resume checkpoints</button><button disabled={busy || !running} onClick={() => void act('cancel')}>Cancel campaign</button></div>
    <p>Source evidence: {result?.request?.benchmark_complete ? 'complete' : 'partial benchmark; only passing bounded families included'}. Verdict: {state.scientific_verdict}. Queue time is separate from the training budget.</p>
    <table><thead><tr><th>Frozen family</th><th>Tested anchor EVs</th><th>Controller</th></tr></thead><tbody>{Object.entries(result?.request?.anchors || {}).map(([family, a]) => <tr key={family}><td>{family}</td><td>{(a as J).fleet_size}</td><td>{(a as J).strategy}</td></tr>)}</tbody></table>
    <p>{result?.report?.trials?.length || 0} training records · {result?.report?.evaluation?.filter((b: J) => b.complete).length || 0} complete held-out blocks. Partial blocks cannot establish improvement.</p>
    {result?.report?.summary && <pre>{JSON.stringify(result.report.summary, null, 2)}</pre>}</>}
  </section>;
}
