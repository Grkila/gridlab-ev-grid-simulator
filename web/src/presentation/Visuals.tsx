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
const number = (value: number, digits = 0) => value.toLocaleString('sr-Latn-RS', {minimumFractionDigits:digits, maximumFractionDigits:digits});
function Count({value,progress,digits=0}:{value:number;progress:number;digits?:number}) {
  return <span className="animated-number" data-target={value} aria-label={number(value,digits)}><span aria-hidden="true">{number(digits ? value*progress : Math.round(value*progress),digits)}</span></span>;
}

export function Visual({slide,active,reduced}:{slide:Slide;active:boolean;reduced:boolean}) {
  const progress=useRevealProgress(active,reduced);
  if(slide.id==='capacity-aware-inputs')return <ControlDiagram/>;
  if(slide.kind==='mcp-demo')return <MCPDemo active={active} reduced={reduced} codex={slide.id==='assistant'}/>;
  if(slide.kind==='bars')return <DailyEnergy progress={progress}/>;
  if(slide.kind==='compare')return <div className="location-study" aria-label="Poređenje vršne snage za 1.000 vozila: kod kuće 149,24 MW, na poslu 145,41 MW, javno 146,76 MW.">
    <div className="study-context"><span>ISTA STUDIJA</span><b>1.000 vozila · 14 MWh</b><p>Sva tri scenarija prolaze kroz tri semena.</p></div>
    <div className="location-peaks">
      {([['Kod kuće','149,24','Večernji dolasci podižu vrh.'],['Na poslu','145,41','Boravak tokom dana ostavlja više prostora.'],['Javno','146,76','Deset pretpostavljenih lokacija.']] as const).map(([name,value,detail],i)=><article key={name} style={{'--peak':`${[96,72,82][i]}%` } as CSSProperties}><span>0{i+1}</span><h2>{name}</h2><strong>{value}<small> MW</small></strong><div className="peak-meter"><i/></div><p>{detail}</p></article>)}
    </div>
    <div className="location-takeaway">Najniži vrh u studiji: punjenje na poslu. Lokacija i vreme menjaju rezultat, ne samo broj vozila.</div>
    <p className="chart-note">Javno punjenje koristi pretpostavljene čvorove; zato studija odvojeno proverava uticaj vremena i lokacije. Ovo nisu izmerene navike vozača.</p>
  </div>;
  if(slide.id==='critical')return <div className="concurrency-chart" aria-label="Istovremeno punjenje: u 03:00 10.044 vozila, u 18:00 8.618, u 20:00 6.516.">
    {([['03:00',10044],['18:00',8618],['20:00',6516]] as const).map(([time,value])=><div className="concurrency-column" key={time}><b><Count value={value} progress={progress}/></b><div className="column-track"><i style={{height:`${value/11000*100*progress}%`}}/></div><span>{time}</span></div>)}
    <p className="chart-note">Za isti raspored po mreži. Sledeći broj vozila prelazi zbirno NN ograničenje.</p>
  </div>;
  if(slide.id==='policy')return <LocationPolicy policy><div className="policy-chart" aria-label="Vrh potrošnje za 10.000 vozila: neposredno 183,29 MW, nasumično odlaganje 145,41 MW, popunjavanje dolina 153,87 MW, svi od 23:00 201,70 MW uz pad mrežne provere.">
    {([['Odmah',183.29,true],['Nasumično odlaganje',145.41,true],['Popunjavanje dolina',153.87,true],['Svi od 23:00',201.70,false]] as const).map(([name,value,passed])=><div className={`policy-row ${passed?'':'failed'}`} key={name}><span>{name}</span><div className="bar-track"><i style={{width:`${value/220*100*progress}%`}}/></div><b><Count value={value} digits={2} progress={progress}/> <small>MW</small></b><em>{passed?'Prolazi':'Ne prolazi'}</em></div>)}
    <p className="chart-note">Gornji vrh kroz tri semena. Svaka politika isporučuje 140.000 kWh.<br/>Punjenje od 23:00 ne prolazi mrežne provere ni na jednom semenu.</p>
  </div></LocationPolicy>;
  if(slide.id==='admission')return <div className="admission-strategy" aria-label="Strategija prijema proverava slobodnu snagu, energiju do odlaska i mrežna ograničenja pre prihvatanja vozila.">
    <div className="admission-input"><span>ZAHTEV VOZILA</span><b>14 kWh</b><p>Odlazak u 07:00 · punjač 7,4 kW</p></div>
    <div className="admission-checks"><article><span>01</span><b>Slobodna snaga</b><p>Uračunaj već prihvaćeno punjenje.</p></article><article><span>02</span><b>Dovoljno vremena</b><p>Da li energija staje pre odlaska?</p></article><article><span>03</span><b>Mrežna provera</b><p>Bez prelaska ograničenja modela.</p></article></div>
    <div className="admission-outcome"><div><span>ODLUKA</span><strong>PRIMI I RASPOREDI</strong></div><p>Ako jedan uslov ne prolazi: ponudi nižu snagu, drugi termin ili odbij zahtev.</p></div>
    <p className="chart-note">Slobodna snaga sada nije dovoljna sama po sebi: pri 7,4 kW i 90% efikasnosti jedan sat isporučuje samo 6,66 kWh.</p>
  </div>;
  if(slide.kind==='app')return <div className="app-placeholder"><span>GRIDLAB</span><p>{slide.label}</p><small>Interaktivna aplikacija</small></div>;
  if(slide.items)return <div className={`story-items ${slide.kind==='flow'?'flow-items':''} ${slide.kind==='limits'?'limit-items':''}`}>
    {slide.items.map((item,i)=><div className="story-item" key={item} style={{'--order':i} as CSSProperties}><span className="item-number">{String(i+1).padStart(2,'0')}</span><p>{item}</p>{slide.kind==='flow'&&i<slide.items!.length-1&&<span className="flow-arrow">↗</span>}</div>)}
  </div>;
  return null;
}
