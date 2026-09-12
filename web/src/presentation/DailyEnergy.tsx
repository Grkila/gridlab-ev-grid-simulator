import {useState} from 'react';
import data from './dailyEnergy.json';

export function DailyEnergy({progress}:{progress:number}){
  const [battery,setBattery]=useState(60);
  const row=data.variants.find(v=>v.battery_kwh===battery)!;
  const num=(n:number,d=0)=>n.toLocaleString('en-GB',{maximumFractionDigits:d,minimumFractionDigits:d});
  return <div className="daily-energy">
    <div className="energy-choice"><span>Full battery · 0 → 100%</span>{data.variants.map(v=><button key={v.battery_kwh} aria-pressed={battery===v.battery_kwh} onClick={()=>setBattery(v.battery_kwh)}>{v.battery_kwh} kWh</button>)}</div>
    <div className="energy-columns">
      <article><small>IDEAL ENERGY BOUND / 24 HOURS</small><strong>{num(Math.floor(row.full_charges_upper_bound*progress))}<em>maximum full charges per day</em></strong><p>{num(row.grid_kwh_per_car,1)} kWh from charger per vehicle<br/>{num(row.hours_at_7_4kw,1)} h at a 7.4 kW charger</p><b>An energy calculation, not demonstrated service.</b></article>
      <article><small>JUNE / CHARGING HEADROOM</small><div className="energy-line"><span>City baseline energy, including losses</span><b>2,565.5 MWh</b></div><div className="energy-line"><span>Remaining aggregate LV energy budget</span><b>1,611.5 MWh</b></div><div className="energy-line"><span>Battery energy at 90% efficiency</span><b>1,450.3 MWh</b></div><p className="energy-formula">1,450,318 kWh ÷ {battery} kWh<br/>= at most {num(row.full_charges_upper_bound)} full batteries</p></article>
    </div>
    <div className="energy-evidence"><b><span className="animated-number" data-target="48000"><span>{num(Math.floor(48000*progress))}</span></span> vehicles → 623–637 groups</b><span>Home scenario: 14 kWh per vehicle, three seeds, 33-hour horizon.</span></div>
    <p className="energy-benchmark">Benchmark: 65,544 vehicles × 14 kWh. Different conditions. Provisional result with failed final status.</p>
    <p className="chart-note">LV budget: 120 MW minus 50% of baseline load. Local limits, losses, and deadlines can reduce this bound. Synthetic model.</p>
  </div>;
}
