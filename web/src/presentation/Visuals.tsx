import {LocationPolicy} from './LocationPolicy';
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
const number = (value: number, digits = 0) => value.toLocaleString('sr-Latn-RS', {minimumFractionDigits:digits, maximumFractionDigits:digits});
function Count({value,progress,digits=0}:{value:number;progress:number;digits?:number}) {
  return <span className="animated-number" data-target={value} aria-label={number(value,digits)}><span aria-hidden="true">{number(digits ? value*progress : Math.round(value*progress),digits)}</span></span>;
}

export function Visual({slide,active,reduced}:{slide:Slide;active:boolean;reduced:boolean}) {
  const progress=useRevealProgress(active,reduced);
  if(slide.kind==='mcp-demo')return <MCPDemo active={active} reduced={reduced} codex={slide.id==='assistant'}/>;
  if(slide.kind==='bars')return <DailyEnergy progress={progress}/>;
  if(slide.kind==='compare')return <LocationPolicy><div className="comparison"><div><span>KOD KUĆE</span><strong><Count value={149.24} digits={2} progress={progress}/><sub> MW</sub></strong><div className="mini-meter"><i style={{width:`${149.24/160*100*progress}%`}}/></div><p>Gornji vrh kroz tri semena</p></div><span className="compare-arrow">→</span><div><span>NA POSLU</span><strong><Count value={145.41} digits={2} progress={progress}/><sub> MW</sub></strong><div className="mini-meter"><i style={{width:`${145.41/160*100*progress}%`}}/></div><p>Sva tri semena prolaze</p></div><small>Ista energija: 14.000 kWh. Kućni vrh: 149,02–149,24 MW.<br/>Pretpostavljeni rasporedi i lokacije, ne izmerene navike.</small></div></LocationPolicy>;
  if(slide.id==='critical')return <div className="concurrency-chart" aria-label="Istovremeno punjenje: u 03:00 10.044 vozila, u 18:00 8.618, u 20:00 6.516.">
    {([['03:00',10044],['18:00',8618],['20:00',6516]] as const).map(([time,value])=><div className="concurrency-column" key={time}><b><Count value={value} progress={progress}/></b><div className="column-track"><i style={{height:`${value/11000*100*progress}%`}}/></div><span>{time}</span></div>)}
    <p className="chart-note">Za isti raspored po mreži. Sledeći broj vozila prelazi zbirno NN ograničenje.</p>
  </div>;
  if(slide.id==='policy')return <LocationPolicy policy><div className="policy-chart" aria-label="Vrh potrošnje za 10.000 vozila: neposredno 183,29 MW, nasumično odlaganje 145,41 MW, popunjavanje dolina 153,87 MW, svi od 23:00 201,70 MW uz pad mrežne provere.">
    {([['Odmah',183.29,true],['Nasumično odlaganje',145.41,true],['Popunjavanje dolina',153.87,true],['Svi od 23:00',201.70,false]] as const).map(([name,value,passed])=><div className={`policy-row ${passed?'':'failed'}`} key={name}><span>{name}</span><div className="bar-track"><i style={{width:`${value/220*100*progress}%`}}/></div><b><Count value={value} digits={2} progress={progress}/> <small>MW</small></b><em>{passed?'Prolazi':'Ne prolazi'}</em></div>)}
    <p className="chart-note">Gornji vrh kroz tri semena. Svaka politika isporučuje 140.000 kWh.<br/>Punjenje od 23:00 ne prolazi mrežne provere ni na jednom semenu.</p>
  </div></LocationPolicy>;
  if(slide.kind==='app')return <div className="app-placeholder"><span>GRIDLAB</span><p>{slide.label}</p><small>Interaktivna aplikacija</small></div>;
  if(slide.items)return <div className={`story-items ${slide.kind==='flow'?'flow-items':''} ${slide.kind==='limits'?'limit-items':''}`}>
    {slide.items.map((item,i)=><div className="story-item" key={item} style={{'--order':i} as CSSProperties}><span className="item-number">{String(i+1).padStart(2,'0')}</span><p>{item}</p>{slide.kind==='flow'&&i<slide.items!.length-1&&<span className="flow-arrow">↗</span>}</div>)}
  </div>;
  return null;
}
