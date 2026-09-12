import {LocationPolicy} from './LocationPolicy';
import {ControlDiagram} from './ControlDiagram';
import {DailyEnergy} from './DailyEnergy';
import {MCPDemo} from './MCPDemo';
import { useEffect, useState, type CSSProperties } from 'react';
import type { Slide } from './slides';

function useRevealProgress(active: boolean, reduced: boolean) {
  const [progress, setProgress] = useState(reduced ? 1 : 0);
  useEffect(() => {
    if (reduced) { setProgress(1); return; }
    setProgress(0);
    if (!active) return;
    let raf = 0;
    const start = performance.now();
    const tick = (time: number) => {
      const fraction = Math.min(1, (time - start) / 1450);
      setProgress(1 - (1 - fraction) ** 3);
      if (fraction < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, reduced]);
  return progress;
}
const number = (value: number, digits = 0) => value.toLocaleString('en-GB', {minimumFractionDigits:digits, maximumFractionDigits:digits});
function Count({value,progress,digits=0}:{value:number;progress:number;digits?:number}) {
  return <span className="animated-number" data-target={value} aria-label={number(value,digits)}><span aria-hidden="true">{number(digits ? value*progress : Math.round(value*progress),digits)}</span></span>;
}

export function Visual({slide,active,reduced}:{slide:Slide;active:boolean;reduced:boolean}) {
  const progress=useRevealProgress(active,reduced);
  if(slide.id==='capacity-aware-inputs')return <ControlDiagram/>;
  if(slide.kind==='mcp-demo')return <MCPDemo active={active} reduced={reduced} codex={slide.id==='assistant'}/>;
  if(slide.kind==='bars')return <DailyEnergy progress={progress}/>;
  if(slide.kind==='compare')return <div className="location-study" aria-label="Peak supply for 1,000 vehicles: home 149.24 MW, workplace 145.41 MW, public 146.76 MW.">
    <div className="study-context"><span>SAME STUDY</span><b>1,000 vehicles · 14 MWh</b><p>All three scenarios pass across three seeds.</p></div>
    <div className="location-peaks">
      {([['Home','149.24','Evening arrivals increase the peak.'],['Workplace','145.41','Daytime parking provides scheduling flexibility.'],['Public','146.76','Ten assumed locations.']] as const).map(([name,value,detail],i)=><article key={name} style={{'--peak':`${[96,72,82][i]}%` } as CSSProperties}><span>0{i+1}</span><h2>{name}</h2><strong>{value}<small> MW</small></strong><div className="peak-meter"><i/></div><p>{detail}</p></article>)}
    </div>
    <div className="location-takeaway">Workplace charging gives the lowest study peak. Both location and timing affect this result.</div>
    <p className="chart-note">Public charging uses assumed nodes. Separate controls examine timing and location. These schedules are not measured driver behavior.</p>
  </div>;
  if(slide.id==='critical')return <div className="concurrency-chart" aria-label="Simultaneous charging: 10,044 vehicles at 03:00, 8,618 at 18:00, and 6,516 at 20:00.">
    {([['03:00',10044],['18:00',8618],['20:00',6516]] as const).map(([time,value])=><div className="concurrency-column" key={time}><b><Count value={value} progress={progress}/></b><div className="column-track"><i style={{height:`${value/11000*100*progress}%`}}/></div><span>{time}</span></div>)}
    <p className="chart-note">The network allocation stays fixed. Each next integer exceeds the aggregate LV limit.</p>
  </div>;
  if(slide.id==='policy')return <LocationPolicy policy><div className="policy-chart" aria-label="Peak supply for 10,000 vehicles: immediate 183.29 MW, randomized delay 145.41 MW, valley filling 153.87 MW, fixed delay 201.70 MW. Fixed delay fails grid checks.">
    {([['Immediate',183.29,true],['Randomized delay',145.41,true],['Valley filling',153.87,true],['All start at 23:00',201.70,false]] as const).map(([name,value,passed])=><div className={`policy-row ${passed?'':'failed'}`} key={name}><span>{name}</span><div className="bar-track"><i style={{width:`${value/220*100*progress}%`}}/></div><b><Count value={value} digits={2} progress={progress}/> <small>MW</small></b><em>{passed?'Pass':'Fail'}</em></div>)}
    <p className="chart-note">Highest peak across three seeds. Each policy delivers 140,000 kWh.<br/>The 23:00 start fails grid checks for every seed.</p>
  </div></LocationPolicy>;
  if(slide.id==='admission')return <div className="admission-strategy" aria-label="Admission checks available power, energy before departure, and grid limits before accepting a vehicle.">
    <div className="admission-input"><span>VEHICLE REQUEST</span><b>14 kWh</b><p>Departure 07:00 · 7.4 kW charger</p></div>
    <div className="admission-checks"><article><span>01</span><b>Available power</b><p>Include accepted charging requests.</p></article><article><span>02</span><b>Enough time</b><p>Can charging finish before departure?</p></article><article><span>03</span><b>Grid check</b><p>Stay within the modeled limits.</p></article></div>
    <div className="admission-outcome"><div><span>DECISION</span><strong>ACCEPT AND SCHEDULE</strong></div><p>If a condition fails, offer less power, another time, or reject the request.</p></div>
    <p className="chart-note">Available power alone is insufficient. At 7.4 kW and 90% efficiency, one hour delivers only 6.66 kWh.</p>
  </div>;
  if(slide.kind==='app')return <div className="app-placeholder"><span>GRIDLAB</span><p>{slide.label}</p><small>Interactive application</small></div>;
  if(slide.items)return <div className={`story-items ${slide.kind==='flow'?'flow-items':''} ${slide.kind==='limits'?'limit-items':''}`}>
    {slide.items.map((item,i)=><div className="story-item" key={item} style={{'--order':i} as CSSProperties}><span className="item-number">{String(i+1).padStart(2,'0')}</span><p>{item}</p>{slide.kind==='flow'&&i<slide.items!.length-1&&<span className="flow-arrow">↗</span>}</div>)}
  </div>;
  return null;
}
