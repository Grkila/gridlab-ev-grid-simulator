import {useEffect, useState} from 'react';

const steps = [
  {role:'YOU',title:'Create an experiment',text:'Create a June experiment with 10,000 vehicles, home charging, seed 41001, and four strategies. Save the definition. Start the simulation.'},
  {role:'AGENT',title:'Read the contract and model',text:'Keep conditions and energy requests identical across strategies.',tool:'ev_get_contract → ev_get_catalog',code:'client_version: "1.0.0"\nmodel: reduced_pandapower'},
  {role:'MCP TOOL',title:'Save the experiment',text:'The tool checks the definition and saves an experiment with a stable identifier.',tool:'ev_save_experiment',code:'definition: {\n  fleet: { fleet_size: 10000, charging_profile: "home_only", … },\n  demand: { month: 6, … }, seeds: [41001],\n  strategies: ["immediate", "fixed_delay",\n               "randomized_delay", "capacity_aware"], …\n}',result:'experiment_id: exp-bf08b8697388a90cc36f'},
  {role:'MCP TOOL',title:'Start and monitor',text:'The simulator executes the cases. The agent reads their status.',tool:'ev_start_run → ev_get_run',code:'experiment_id: exp-bf08b8697388a90cc36f',result:'run-3484553ec8bb4a5f · completed · 4 cases'},
  {role:'YOU → MCP',title:'Compare the results',text:'Compare the strategies in this experiment. Show peak demand and delivered energy. The agent reads the saved results.',tool:'ev_get_results',code:'run_id: "run-3484553ec8bb4a5f"\ninclude_intervals: false'},
  {role:'AGENT',title:'Compare matched conditions',text:'All four strategies deliver 140,000 kWh. Randomized delay gives a 145.407 MW peak. Fixed delay gives a new 201.596 MW peak.',result:'Saved inputs + seed + results · repeatable checks'},
];

export function MCPDemo({active,reduced,codex}:{active:boolean;reduced:boolean;codex:boolean}){
  const [step,setStep]=useState(0);
  const [view,setView]=useState<'tools'|'chat'|'algorithm'>('tools');
  useEffect(()=>{if(active){setStep(0);setView('tools');}},[active]);
  const selected=steps[step];
  return <div className="mcp-demo-panel">
    <div className="mcp-demo-toolbar"><strong>{codex?'Codex / EV Hypothesis Playground':'MCP demo / chat · Codex · terminal'}</strong><span>PREPARED DEMO · no execution</span></div>
    <div className="mcp-demo-tabs">{([['tools','MCP tool sequence'],['chat','Chat interface'],['algorithm','Algorithm development']] as const).map(([id,label])=><button key={id} aria-pressed={view===id} onClick={()=>setView(id)}>{label}</button>)}<span>Click to change the view</span></div>
    {view==='tools'?<div className="mcp-demo-body">
      <nav className="mcp-demo-history" aria-label="MCP demonstration steps">
        <small>{codex?'PLUGIN CONNECTS THE PROJECT':'REQUEST AND TOOL HISTORY'}</small>
        {steps.map((entry,i)=><button key={entry.title} className={step===i?'selected':''} aria-current={step===i?'step':undefined} onClick={()=>{setStep(i);}}><b>{i<step?'✓':String(i+1).padStart(2,'0')}</b><span>{entry.title}<small>{entry.role}</small></span></button>)}
        <p>{codex?'Codex → plugin → local MCP → simulator. The web application can remain closed.':'The Codex plugin connects the local project and simulator. Chat uses the same MCP tools.'}</p>
      </nav>
      <article className="mcp-demo-message" key={step}>
        <small>{selected.role} / {step+1} OF {steps.length}</small><h2>{selected.title}</h2><p>{selected.text}</p>
        {selected.tool&&<div className="mcp-tool"><strong>↗ {selected.tool}</strong><pre>{selected.code}</pre><small>Abbreviated arguments</small></div>}
        {selected.result&&<div className="mcp-tool-result"><span>✓ SAVED EVIDENCE</span><p>{selected.result}</p></div>}
        {step===0&&<div className="mcp-tool-result"><span>{codex?'INSTALLED PROJECT PLUGIN':'CONVERSATION CONTEXT'}</span><p>{codex?'Research skill + MCP tools + local project':'Model · scenario · strategies · tool history'}</p></div>}
      </article>
    </div>:<div className={`mcp-gui-preview gui-${view}`}><div><small>ACTUAL APPLICATION CAPTURE</small><h2>{view==='chat'?'Chat with the agent':'From idea to algorithm'}</h2><p>{view==='chat'?'Prompt, conversation history, task selection, and saved tool calls.':'Proposal → specification → implementation → comparison.'}</p><p>{view==='chat'?'The prompt is prepared and unsent.':'A structured command saves conditions and prepares work for the agent.'}</p></div><img src={`/presentation/${view==='chat'?'chat':'algorithm'}-interface.png`} alt={view==='chat'?'Actual GridLab chat with an unsent prompt':'Actual algorithm proposal and development form'}/></div>}
    <footer><span>Prepared playback · no messages or tool execution</span><button onClick={()=>{setView('tools');setStep(0);}}>Reset</button><button disabled={view!=='tools'||step===0} onClick={()=>setStep(v=>v-1)}>Previous step</button><button disabled={view!=='tools'||step===steps.length-1} onClick={()=>setStep(v=>v+1)}>Next step</button></footer>
  </div>;
}
