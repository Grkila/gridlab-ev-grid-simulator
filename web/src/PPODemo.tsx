import { usePresentationCue } from './presentation/bridge';
import { useEffect, useState } from 'react';

import episodeData from './ppo-demo-episodes.json';

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';



// Presentation fixtures only. Never submitted to training or benchmark APIs.

const scenarios = {

  normal: { name: 'Typical day', cars: 12000, energy: 168000, peak: 218.4, start: 268.2 },

  winter: { name: 'Winter day', cars: 8000, energy: 112000, peak: 236.8, start: 279.6 },

  district: { name: 'Single district', cars: 1500, energy: 21000, peak: 26.2, start: 34.8 },

};

type Scenario = keyof typeof scenarios;

const format = (value: number) => value.toLocaleString('en-US', { maximumFractionDigits: 1 });



export function PPODemo() {

  const [scenario, setScenario] = useState<Scenario>('normal');

  const [checkpoint, setCheckpoint] = useState(100);

  const [playing, setPlaying] = useState(false);

  const [speed, setSpeed] = useState(1);
  const cue=usePresentationCue();
  useEffect(()=>{if(cue?.view==='rl' && cue.section==='demo' && !cue.reducedMotion && !matchMedia('(prefers-reduced-motion: reduce)').matches){setCheckpoint(0);setPlaying(true);}else if(cue){setPlaying(false);}},[cue]);

  useEffect(() => {

    if (!playing || checkpoint >= 100) return;

    const timer = window.setTimeout(() => setCheckpoint(value => Math.min(100, value + 1)), 400 / speed);

    return () => window.clearTimeout(timer);

  }, [playing, checkpoint, speed]);

  const running = playing && checkpoint < 100;

  const selected = scenarios[scenario];

  const rows = episodeData.scenarios[scenario];

  const current = rows[checkpoint];

  return <section className="panel rl-training-form ppo-showcase" aria-label="PPO showcase — Demo data">

    <p className="eyebrow">PPO showcase · Demo data</p>

    <h2>Learning to schedule EV charging</h2>

    <p>Synthetic learning curves and illustrative outcomes for this interactive showcase. No training or network simulation is executed here.</p>

    <div className="ppo-controls"><div className="rl-fields">

      <label>Controller<select value="ppo" onChange={() => {}}><option value="ppo">PPO</option></select></label>

      <label>Scenario<select value={scenario} onChange={event => { setScenario(event.target.value as Scenario); setPlaying(false); }}>

        {Object.entries(scenarios).map(([key, value]) => <option key={key} value={key}>{value.name}</option>)}

      </select></label>

    </div>

    <h3>Training progress · Demo data</h3>

    <div className="rl-fields">

      <button onClick={() => { if (checkpoint >= 100) setCheckpoint(0); setPlaying(!running); }}>

        {running ? 'Pause demo' : checkpoint >= 100 ? 'Replay training demo' : 'Start training demo'}

      </button>

      <button onClick={() => { setPlaying(false); setCheckpoint(0); }}>Reset demo</button>

      <label>Playback speed<select value={speed} onChange={event => setSpeed(Number(event.target.value))}>

        <option value={1}>1× · 40 seconds</option><option value={2}>2× · 20 seconds</option><option value={4}>4× · 10 seconds</option>

      </select></label>

    </div>

    <progress aria-label="Demo training progress" max={100} value={checkpoint} style={{ width: '100%', accentColor: '#16795e' }} />

    <p role="status">{checkpoint === 100 ? 'Demo complete' : running ? 'Playing training demo' : checkpoint === 0 ? 'Ready to demonstrate' : 'Demo paused'} · {checkpoint}% · Episode {checkpoint} / 100 · {format(current.step)} / 13,200 steps</p>

    <p>Stage: {checkpoint < 15 ? 'Exploring charging decisions' : checkpoint < 50 ? 'Learning energy and grid constraints' : checkpoint < 80 ? 'Refining charging schedules' : checkpoint < 100 ? 'Stable reward plateau' : 'Converged'}. Synthetic reward: <b>{current.reward}</b>. Playback does not run PPO.</p>

    <label>Illustrative training checkpoint · {format(current.step)} steps

      <input type="range" min="0" max="100" value={checkpoint} onChange={event => { setPlaying(false); setCheckpoint(Number(event.target.value)); }} />

    </label>

    </div><div className="ppo-evidence"><div className="rl-fields" aria-live="polite">

      <div><b>{format(current.served)} / {format(selected.cars)}</b><p>Cars fully served · demo</p></div>

      <div><b>{format(current.delivered)} kWh</b><p>Delivered of {format(selected.energy)} kWh · demo</p></div>

      <div><b>{format(current.peak)} MW</b><p>Peak grid demand · demo</p></div>

      <div><b>{current.violations}</b><p>Grid violation intervals · demo</p></div>

    </div>

    <p role="status"><b>{checkpoint >= 80 ? 'Converged learning curve · Demo data' : 'Learning in progress · Demo data'}</b>{checkpoint >= 80 && ' — 100% of cars served, all requested energy delivered, zero grid violation intervals.'}</p>

    <p>Episode reward: <b>{current.reward}</b>  -  10-episode mean: <b>{current.rolling_reward}</b>  -  Demo data</p>

    <h3>Learning curve · Demo data</h3>

    <div className="rl-chart" role="img" aria-label={`Synthetic PPO reward curve through ${current.step} steps. Current illustrative reward ${current.reward}.`}>

      <ResponsiveContainer width="100%" height="100%"><LineChart data={rows.slice(0, checkpoint + 1)} margin={{ top: 12, right: 24, bottom: 20, left: 8 }}>

        <CartesianGrid stroke="#e4ede7" vertical={false} />

        <XAxis dataKey="episode" type="number" domain={[0, 100]} label={{ value: 'Episode (synthetic)', position: 'insideBottom', offset: -12 }} />

        <YAxis domain={[-200, 50]} width={55} />

        <Tooltip labelFormatter={value => `Episode ${format(Number(value))} · Demo data`} />

        <Line dataKey="rolling_reward" name="10-episode mean reward" stroke="#3662a3" strokeWidth={2} dot={false} isAnimationActive={false} />

        <Line dataKey="reward" name="Episode reward (demo)" stroke="#16795e" strokeWidth={3} dot={checkpoint === 0} isAnimationActive={false} />

      </LineChart></ResponsiveContainer>

    </div>

    <details><summary>Episode records  -  Demo data</summary>

      <table><thead><tr><th>Episode</th><th>Reward</th><th>10-episode mean</th><th>Delivered kWh</th><th>Unmet kWh</th><th>Violations</th></tr></thead>

      <tbody>{rows.slice(Math.max(0, checkpoint - 9), checkpoint + 1).map(row => <tr key={row.episode}><td>{row.episode}</td><td>{row.reward}</td><td>{row.rolling_reward}</td><td>{format(row.delivered)}</td><td>{format(row.unmet_energy_kwh)}</td><td>{row.violations}</td></tr>)}</tbody></table>

    </details>

    <p>Requested minus delivered energy: <b>{format(selected.energy - current.delivered)} kWh</b> · Demo data. These values are not measured benchmarks or a Novi Sad network-capacity estimate.</p>

    </div>
  </section>;

}


