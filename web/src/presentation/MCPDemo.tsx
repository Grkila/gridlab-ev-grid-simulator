import {useEffect, useState} from 'react';

const steps = [
  {role:'TI',title:'Napravi eksperiment',text:'Napravi eksperiment za 10.000 vozila u junu: kućno punjenje, seme 41001 i četiri strategije. Sačuvaj ga, pa pokreni simulaciju.'},
  {role:'AGENT',title:'Uzimam ugovor i početni model',text:'Zadržavam iste uslove i traženu energiju za sve strategije.',tool:'ev_get_contract → ev_get_catalog',code:'client_version: "1.0.0"\nmodel: reduced_pandapower'},
  {role:'MCP ALAT',title:'Pravljenje eksperimenta',text:'Alat proverava definiciju i čuva eksperiment sa stabilnim identifikatorom.',tool:'ev_save_experiment',code:'definition: {\n  fleet: { fleet_size: 10000, charging_profile: "home_only", … },\n  demand: { month: 6, … }, seeds: [41001],\n  strategies: ["immediate", "fixed_delay",\n               "randomized_delay", "capacity_aware"], …\n}',result:'experiment_id: exp-bf08b8697388a90cc36f'},
  {role:'MCP ALAT',title:'Pokretanje i praćenje',text:'Simulator izvršava slučajeve; agent čita status.',tool:'ev_start_run → ev_get_run',code:'experiment_id: exp-bf08b8697388a90cc36f',result:'run-3484553ec8bb4a5f · completed · 4 slučaja'},
  {role:'TI → MCP',title:'Sada pripremi poređenje',text:'„Uporedi rezultate strategija u ovom eksperimentu. Prikaži vrh potrošnje i isporučenu energiju.“ Agent čita sačuvane rezultate.',tool:'ev_get_results',code:'run_id: "run-3484553ec8bb4a5f"\ninclude_intervals: false'},
  {role:'AGENT',title:'Poređenje na istim uslovima',text:'Sve četiri strategije isporučuju 140.000 kWh. Nasumično odlaganje smanjuje vrh na 145,407 MW; fiksno odlaganje pravi novi vrh od 201,596 MW.',result:'Sačuvani ulazi + seme + rezultati · ponovljiva provera'},
];

export function MCPDemo({active,reduced,codex}:{active:boolean;reduced:boolean;codex:boolean}){
  const [step,setStep]=useState(0);
  const [view,setView]=useState<'tools'|'chat'|'algorithm'>('tools');
  useEffect(()=>{if(active){setStep(0);setView('tools');}},[active]);
  const selected=steps[step];
  return <div className="mcp-demo-panel">
    <div className="mcp-demo-toolbar"><strong>{codex?'Codex / EV Hypothesis Playground':'MCP demo / chat · Codex · terminal'}</strong><span>PRIPREMLJEN DEMO · bez izvršavanja</span></div>
    <div className="mcp-demo-tabs">{([['tools','Tok MCP alata'],['chat','Chat interfejs'],['algorithm','Kreiranje algoritma']] as const).map(([id,label])=><button key={id} aria-pressed={view===id} onClick={()=>setView(id)}>{label}</button>)}<span>Prikaz se menja samo na klik</span></div>
    {view==='tools'?<div className="mcp-demo-body">
      <nav className="mcp-demo-history" aria-label="Koraci MCP demonstracije">
        <small>{codex?'PLUGIN JE VEZA SA PROJEKTOM':'ISTORIJA ZAHTEVA I ALATA'}</small>
        {steps.map((entry,i)=><button key={entry.title} className={step===i?'selected':''} aria-current={step===i?'step':undefined} onClick={()=>{setStep(i);}}><b>{i<step?'✓':String(i+1).padStart(2,'0')}</b><span>{entry.title}<small>{entry.role}</small></span></button>)}
        <p>{codex?'Codex → plugin → lokalni MCP → simulator. Veb-aplikacija ne mora da bude otvorena.':'Codex plugin povezuje lokalni projekat i simulator. Isti MCP alati dostupni su i iz chata.'}</p>
      </nav>
      <article className="mcp-demo-message" key={step}>
        <small>{selected.role} / {step+1} OD {steps.length}</small><h2>{selected.title}</h2><p>{selected.text}</p>
        {selected.tool&&<div className="mcp-tool"><strong>↗ {selected.tool}</strong><pre>{selected.code}</pre><small>Skraćen prikaz argumenata</small></div>}
        {selected.result&&<div className="mcp-tool-result"><span>✓ SAČUVANA EVIDENCIJA</span><p>{selected.result}</p></div>}
        {step===0&&<div className="mcp-tool-result"><span>{codex?'INSTALIRAN PROJEKTNI PLUGIN':'KONTEKST RAZGOVORA'}</span><p>{codex?'Skill za istraživanje + MCP alati + lokalni projekat':'Model · scenario · strategije · istorija poziva'}</p></div>}
      </article>
    </div>:<div className={`mcp-gui-preview gui-${view}`}><div><small>SNIMAK STVARNE APLIKACIJE</small><h2>{view==='chat'?'Razgovor sa agentom':'Od ideje do algoritma'}</h2><p>{view==='chat'?'Zahtev, istorija razgovora, izbor zadatka i sačuvani pozivi alata.':'Predlog → specifikacija → implementacija → poređenje.'}</p><p>{view==='chat'?'Poruka je pripremljena, nije poslata.':'Standardna komanda čuva uslove i priprema rad za agenta.'}</p></div><img src={`/presentation/${view==='chat'?'chat':'algorithm'}-interface.png`} alt={view==='chat'?'Stvarni GridLab chat sa pripremljenom porukom':'Stvarni obrazac za predlaganje i kreiranje algoritma'}/></div>}
    <footer><span>Pripremljen prikaz · bez slanja poruka i izvršavanja alata</span><button onClick={()=>{setView('tools');setStep(0);}}>Na početak</button><button disabled={view!=='tools'||step===0} onClick={()=>setStep(v=>v-1)}>Prethodni korak</button><button disabled={view!=='tools'||step===steps.length-1} onClick={()=>setStep(v=>v+1)}>Sledeći korak</button></footer>
  </div>;
}
