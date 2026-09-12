import {useState,type ReactNode} from 'react';

export function LocationPolicy({policy,children}:{policy?:boolean;children:ReactNode}){
  const [evidence,setEvidence]=useState(false);
  const cards=policy?[
    ['Workplace chargers','June estimate: about 18% more energy headroom from 08:00–16:00 than from 16:00–24:00.'],
    ['More charging spaces','More connected vehicles share limited power. More chargers do not increase grid capacity.'],
    ['Public hubs on the MV grid','A dedicated MV connection with its own transformer removes that charging demand from the existing residential LV branch.'],
  ]:[
    ['Home · night','The driver sets a departure time. Schedule charging outside the peak, for example 00:00–06:00, when sufficient.'],
    ['Workplace · daytime','Spread charging across the parking period. The June profile provides more headroom than the evening period.'],
    ['Public and fast chargers','Reduce charging power within permitted limits when local reserve decreases.'],
  ];
  return <div className="location-policy"><div className="mcp-demo-tabs"><button aria-pressed={!evidence} onClick={()=>setEvidence(false)}>{policy?'Expansion proposal':'Control proposal'}</button><button aria-pressed={evidence} onClick={()=>setEvidence(true)}>{policy?'Study results':'Demand-curve estimate'}</button></div>
    {evidence?children:<><div className="location-cards">{cards.map(([title,body],i)=><article key={title}><small>0{i+1}</small><h2>{title}</h2><p>{body}</p></article>)}</div>
    <div className="location-takeaway">{policy?'More choices of place and time support managed expansion.':'Available power + energy before departure → charging schedule.'}</div>
    <p className="chart-note">{policy?'This is an estimate. MV benefits depend on a new transformer and upstream limits. The connection requires investment. Additional chargers need a shared power limit.':'The simulator checks modeled assets every 15 minutes. Real transformer reserve requires detailed data. The 00:00–06:00 window is an example, not a synchronized start.'}</p></>}
  </div>;
}
