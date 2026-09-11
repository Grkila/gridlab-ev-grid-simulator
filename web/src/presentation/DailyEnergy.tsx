import {useState} from 'react';
import data from './dailyEnergy.json';

export function DailyEnergy({progress}:{progress:number}){
  const [battery,setBattery]=useState(60);
  const row=data.variants.find(v=>v.battery_kwh===battery)!;
  const num=(n:number,d=0)=>n.toLocaleString('sr-Latn-RS',{maximumFractionDigits:d,minimumFractionDigits:d});
  return <div className="daily-energy">
    <div className="energy-choice"><span>Cela baterija · 0 → 100%</span>{data.variants.map(v=><button key={v.battery_kwh} aria-pressed={battery===v.battery_kwh} onClick={()=>setBattery(v.battery_kwh)}>{v.battery_kwh} kWh</button>)}</div>
    <div className="energy-columns">
      <article><small>IDEALNA ENERGETSKA GRANICA / 24 SATA</small><strong>{num(Math.floor(row.full_charges_upper_bound*progress))}<em>punjenja dnevno, najviše</em></strong><p>{num(row.grid_kwh_per_car,1)} kWh iz punjača po vozilu<br/>{num(row.hours_at_7_4kw,1)} h na punjaču od 7,4 kW</p><b>Proračun energije, nije potvrđena usluga.</b></article>
      <article><small>JUN / PROSTOR ZA PUNJENJE</small><div className="energy-line"><span>Osnovna energija grada, sa gubicima</span><b>2.565,5 MWh</b></div><div className="energy-line"><span>Preostali zbirni NN energetski budžet</span><b>1.611,5 MWh</b></div><div className="energy-line"><span>U baterije, uz 90% efikasnosti</span><b>1.450,3 MWh</b></div><p className="energy-formula">1.450.318 kWh ÷ {battery} kWh<br/>= najviše {num(row.full_charges_upper_bound)} celih baterija</p></article>
    </div>
    <div className="energy-evidence"><b><span className="animated-number" data-target="48000"><span>{num(Math.floor(48000*progress))}</span></span> vozila → 623–637 grupa</b><span>Kućni scenario: 14 kWh po vozilu, tri semena, horizont 33 h.</span></div>
    <p className="energy-benchmark">Benchmark: 65.544 vozila × 14 kWh. Drugi uslovi; privremen rezultat (failed).</p>
    <p className="chart-note">NN budžet: 120 MW − 50% osnovnog opterećenja. Lokalni limiti, gubici i rokovi mogu smanjiti broj. Sintetički model.</p>
  </div>;
}
