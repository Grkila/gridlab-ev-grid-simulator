import React, {useCallback, useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import Reveal, {type RevealApi} from 'reveal.js';
import 'reveal.js/reveal.css';
import {City} from './City';
import {slides} from './slides';
import {Visual} from './Visuals';
import {cueEvent} from './bridge';
import {preferredDemoRun} from './demoDefaults';
import './presentation.css';
import './revision.css';

const viewNames:Record<string,string>={experiments:'Eksperimenti',results:'Rezultati',network:'Mreža',strategies:'Strategije',benchmarks:'Benčmark',rl:'Obuka',overview:'Pregled'};
const chapters=[...new Set(slides.map(s=>s.chapter))];
const sourceUrl=(source:string)=>`/presentation/sources/${source.replaceAll('/','__')}.txt`;

function Presentation(){
  const element=useRef<HTMLDivElement>(null), iframe=useRef<HTMLIFrameElement>(null), deck=useRef<RevealApi|null>(null);
  const [index,setIndex]=useState(0), [overview,setOverview]=useState(false), [notes,setNotes]=useState(false), [settings,setSettings]=useState(false), [interactive,setInteractive]=useState(true);
  const [reduced,setReduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [runs,setRuns]=useState<{run_id:string;name?:string;status:string}[]>([]),[runId,setRunId]=useState(()=>new URLSearchParams(location.search).get('run')||'');
  const [connection,setConnection]=useState<'checking'|'online'|'offline'>('checking'),[ack,setAck]=useState('');
  const slide=slides[index];
  const current=useRef({index,runId,reduced});current.current={index,runId,reduced};
  const sendCue=useCallback(()=>{
    const {index:position,runId:run}=current.current;
    const cue=slides[position].cue;
    if(cue)iframe.current?.contentWindow?.postMessage({type:cueEvent,cue:{...cue,runId:run||undefined,reducedMotion:current.current.reduced}},location.origin);
  },[]);
  const refresh=useCallback(async()=>{
    setConnection('checking');
    try{
      const [catalogResponse,runsResponse]=await Promise.all([fetch('/api/catalog'),fetch('/api/runs')]);
      if(!catalogResponse.ok||!runsResponse.ok)throw new Error('Backend unavailable');
      const [catalog,data]=await Promise.all([catalogResponse.json(),runsResponse.json()]);
      if(!catalog||!Array.isArray(data))throw new Error('Invalid backend response');
      setRuns(data);setConnection('online');
      setRunId(existing=>existing||preferredDemoRun(data)?.run_id||'');
    }catch{setConnection('offline');}
  },[]);
  useEffect(()=>{void refresh();},[refresh]);
  useEffect(()=>{
    if(!element.current)return;
    const instance=new Reveal(element.current,{width:1600,height:900,margin:0,minScale:0.1,maxScale:2,center:false,controls:false,progress:false,hash:true,hashOneBasedIndex:true,keyboard:false,transition:'fade',transitionSpeed:'fast',backgroundTransition:'fade',embedded:true,scrollActivationWidth:0,autoAnimate:true});
    deck.current=instance;
    instance.on('slidechanged',(event:any)=>{setIndex(event.indexh);setInteractive(true);setAck('');});
    instance.on('overviewshown',()=>{setOverview(true);setInteractive(false);});
    instance.on('overviewhidden',()=>setOverview(false));
    let disposed=false;
    void instance.initialize().then(()=>{if(!disposed)setIndex(instance.getIndices().h);});
    return()=>{disposed=true;deck.current=null;instance.destroy();};
  },[]);
  useEffect(()=>{deck.current?.configure({transition:reduced?'none':'fade',autoAnimate:!reduced});},[reduced]);
  useEffect(()=>{sendCue();},[index,runId,reduced,sendCue]);
  useEffect(()=>{
    const listener=(event:MessageEvent)=>{
      if(event.origin!==location.origin||event.source!==iframe.current?.contentWindow)return;
      if(event.data?.type==='gridlab-presentation-ready')sendCue();
      if(event.data?.type==='gridlab-cue-applied')setAck(event.data.view);
      if(event.data?.type==='gridlab-presentation-key'){
        if(['ArrowRight','PageDown'].includes(event.data.key))deck.current?.next();
        if(['ArrowLeft','PageUp'].includes(event.data.key))deck.current?.prev();
        if(event.data.key==='Escape'){setInteractive(false);iframe.current?.blur();}
      }
    };window.addEventListener('message',listener);return()=>window.removeEventListener('message',listener);
  },[sendCue]);
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{
      if(event.ctrlKey||event.metaKey||event.altKey||(event.target as HTMLElement).closest('input,textarea,select,button,a,[contenteditable="true"]'))return;
      if(['ArrowRight','PageDown',' '].includes(event.key)){event.preventDefault();deck.current?.next();}
      if(['ArrowLeft','PageUp'].includes(event.key)){event.preventDefault();deck.current?.prev();}
      if(event.key==='Home'){event.preventDefault();deck.current?.slide(0);}
      if(event.key==='End'){event.preventDefault();deck.current?.slide(slides.length-1);}
      if(event.key.toLowerCase()==='n')setNotes(v=>!v);
      if(event.key.toLowerCase()==='o')deck.current?.toggleOverview();
      if(event.key.toLowerCase()==='f')void fullscreen();
      if(event.key==='Escape'){setNotes(false);setSettings(false);setInteractive(false);if(deck.current?.isOverview())deck.current.toggleOverview(false);}
    };window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[]);
  const fullscreen=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{/* Browser may disable fullscreen in embedded preview. */}};
  const appVisible=slide.kind==='app'&&!overview;
  const cityScene=[...slides.slice(0,index+1)].reverse().find(s=>s.scene)?.scene||'city';
  return <div className={`presentation ${reduced?'reduced-motion':''} ${overview?'in-overview':''}`}>
    <div className={`city-layer visible background-${slide.kind}`}><City scene={cityScene} reduced={reduced} visible={!overview}/></div><div className={`city-shade shade-${slide.kind}`}/>
    <div className="ambient-orbit"/>
    <header className="deck-header"><a className="deck-brand" href="/" title="Otvori GridLab"><span className="brand-symbol">G<span>↗</span></span>GridLab<span className="brand-divider"/>Istraživanje EV punjenja</a><span className="chapter-label">{slide.chapter}</span><button onClick={()=>setSettings(v=>!v)} aria-label="Podešavanja prezentacije" aria-expanded={settings}>⚙ Podešavanja</button></header>
    <div className="reveal" ref={element}><div className="slides">
      {slides.map((s,i)=><section key={s.id} id={s.id} className={`story-slide kind-${s.kind}`} data-auto-animate={s.kind==='app'?'':undefined}>
        <div className="slide-copy"><p className="slide-eyebrow">{s.question||s.label||s.chapter}</p><h1>{s.title}{s.accent&&<><br/><em>{s.accent}</em></>}</h1><p className="slide-description">{s.body}</p>{s.id==='opening'&&<div className="opening-details"><span className="challenge-label">EV DAYS CHALLENGE</span><p className="team-title">Tim Jokić &amp; Grković<sup>3</sup></p><p className="team-members">Nikola Jokić · Mina Grković · Selena Grković · Dušan Grković</p><div className="schneider-logo"><img src="/presentation/schneider-electric-logo.png" alt="Schneider Electric"/></div></div>}</div>
        <Visual slide={s} active={i===index||overview} reduced={reduced||overview}/>
        {s.references&&<div className="research-references">{s.references.map(ref=><a key={ref.url} href={ref.url} target="_blank" rel="noreferrer">{ref.label} ↗</a>)}</div>}
        {['hero','city','closing'].includes(s.kind)&&<div className="map-caption"><i/> NOVI SAD / 45.2671° N, 19.8335° E<small>Sintetičke tačke · pretpostavljeni vodovi · simbolične visine</small></div>}
        <aside className="notes">{s.note}</aside><span className="print-slide-number">{i+1} / {slides.length}</span>
      </section>)}
    </div></div>
    <div className={`app-stage ${appVisible?'visible':''} ${interactive?'interactive':''} ${slide.id==='chat-demo'?'with-chat-examples':''}`} aria-hidden={!appVisible} inert={!appVisible||undefined}>
      <div className="app-chrome"><span><i className={connection==='online'?'online':''}/>{connection==='online'?'APLIKACIJA UŽIVO':'PRIKAZ APLIKACIJE'}<span className="app-path"> / {viewNames[slide.cue?.view || 'experiments']}{slide.cue?.step!==undefined?` / ${['Scenario','Vozila','Strategije','Pregled'][slide.cue.step]}`:''}</span></span><div><span className="app-sync">{ack===slide.cue?.view?'Prikaz je usklađen':''}</span><button onClick={()=>setInteractive(v=>!v)}>{interactive?'Zaključaj prikaz':'Koristi aplikaciju'}</button><a href={`/?view=${slide.cue?.view||'experiments'}${runId?`&run=${encodeURIComponent(runId)}`:''}`} target="_blank" rel="noreferrer">Otvori ↗</a></div></div>
      {slide.id==='chat-demo'&&<div className="chat-examples"><span>Primer poruke:</span>{[
        ['Objasni eksperiment',`Objasni podešavanja i rezultate eksperimenta ${runId||'koji izaberemo iz kataloga'}. Navedi ograničenja i šta rezultat ne dokazuje. Nemoj pokretati novi eksperiment.`],
        ['Predloži algoritam','Predloži algoritam punjenja koji koristi vreme do odlaska i preostalu energiju. Objasni potrebna opažanja, ograničenja i rezervni postupak. Za sada samo predlog, bez implementacije i pokretanja.'],
        ['Pripremi poređenje','Pripremi plan poređenja neposrednog i upravljanog punjenja: ista vozila, ista semena, isti mrežni model i iste potrebe za energijom. Navedi koje metrike treba proveriti. Za sada ne pokreći eksperimente.']
      ].map(([label,prompt])=><button key={label} onClick={()=>{setInteractive(true);iframe.current?.contentWindow?.postMessage({type:cueEvent,cue:{view:'strategies',section:'development',chat:true,chatPrompt:prompt,runId:runId||undefined}},location.origin);}}>{label}</button>)}<small>Poruka se priprema, a ti biraš kada je šalješ.</small></div>}
      <iframe ref={iframe} title="GridLab interaktivna aplikacija" src="/?present=1&view=experiments" onLoad={sendCue} tabIndex={interactive?0:-1} inert={!interactive||undefined}/>
      {connection!=='online'&&<div className="app-unavailable"><span className="status-ring"/><h2>{connection==='checking'?'Povezivanje sa GridLab-om…':'Server aplikacije nije povezan'}</h2><p>Slajdovi i grafikoni su dostupni. Za rad u aplikaciji pokreni lokalni GridLab server.</p><code>python scripts/run_playground_app.py --port 8517</code><button onClick={()=>{void refresh();iframe.current?.contentWindow?.location.reload();}}>Poveži ponovo</button></div>}
      {connection==='online'&&slide.cue?.view==='results'&&!runId&&<div className="run-prompt"><b>Izaberi sačuvan eksperiment</b><span>Grafikoni u nastavku potiču iz zasebne završene studije.</span><button onClick={()=>setSettings(true)}>Izaberi eksperiment</button></div>}
    </div>
    {settings&&<aside className="deck-panel settings-panel" aria-label="Podešavanja prezentacije"><div className="panel-title"><h2>Podešavanje prezentacije</h2><button onClick={()=>setSettings(false)} aria-label="Zatvori podešavanja">×</button></div><label>Eksperiment za prikaz rezultata<select value={runId} onChange={e=>{setRunId(e.target.value);const url=new URL(location.href);if(e.target.value)url.searchParams.set('run',e.target.value);else url.searchParams.delete('run');history.replaceState(null,'',url);}}><option value="">Izaberi eksperiment</option>{runId&&!runs.some(r=>r.run_id===runId)&&<option value={runId}>{runId} (nije u katalogu)</option>}{runs.map(r=><option key={r.run_id} value={r.run_id}>{r.name||r.run_id} · {r.status}</option>)}</select></label><p>{connection==='online'?`${runs.length} sačuvanih eksperimenata.`:'Pokreni server za pristup eksperimentima.'} Prelazak na slajd ne pokreće eksperiment i ne šalje poruku.</p><button onClick={refresh}>Osveži vezu i eksperimente</button><label className="check-label"><input type="checkbox" checked={reduced} onChange={e=>setReduced(e.target.checked)}/> Smanji animacije</label><a href="/presentation/map.html" target="_blank" rel="noreferrer">Otvori detaljnu mapu ↗</a><p>Za podlogu detaljne mape potreban je internet. 3D prikaz koristi lokalne podatke.</p><div className="shortcuts">← → Slajdovi · O Pregled · N Beleške · F Ceo ekran · Esc Zatvori</div></aside>}
    {notes&&<aside className="deck-panel notes-panel" aria-label="Beleške za izlagača"><div className="panel-title"><h2>{index+1} / Beleške za izlagača</h2><button onClick={()=>setNotes(false)} aria-label="Zatvori beleške">×</button></div><h3>{slide.title} {slide.accent}</h3><p>{slide.note}</p>{slide.source&&<a href={sourceUrl(slide.source)} target="_blank" rel="noreferrer">Izvor: {slide.source} ↗</a>}<p className="next-note">SLEDEĆE / {slides[Math.min(index+1,slides.length-1)].title}</p></aside>}
    <footer className="deck-footer"><div className="chapter-progress">{chapters.map(ch=><button key={ch} className={ch===slide.chapter?'active':''} onClick={()=>deck.current?.slide(slides.findIndex(s=>s.chapter===ch))} title={ch} aria-label={`Otvori: ${ch}`}><span/></button>)}</div><div className="deck-actions"><button onClick={()=>deck.current?.toggleOverview()} aria-label="Pregled slajdova" title="Pregled (O)">▦</button><button onClick={()=>setNotes(v=>!v)} aria-pressed={notes}>Beleške</button><button onClick={fullscreen} title="Ceo ekran (F)">⛶</button><button onClick={()=>deck.current?.prev()} disabled={index===0} aria-label="Prethodni slajd">←</button><select aria-label="Izaberi slajd" value={index} onChange={e=>deck.current?.slide(Number(e.target.value))}>{slides.map((s,i)=><option value={i} key={s.id}>{String(i+1).padStart(2,'0')} / {slides.length} · {s.title}</option>)}</select><button onClick={()=>deck.current?.next()} disabled={index===slides.length-1} aria-label="Sledeći slajd">→</button></div></footer>
    <div className="attribution"><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors · ODbL</a><span>Planski model · kretanje vozila je ilustrativno</span></div>
    <div className="sr-only" aria-live="polite">Slajd {index+1}: {slide.title} {slide.accent}</div>
  </div>;
}
createRoot(document.getElementById('root')!).render(<Presentation/>);
