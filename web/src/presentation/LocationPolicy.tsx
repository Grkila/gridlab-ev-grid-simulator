import {useState,type ReactNode} from 'react';

export function LocationPolicy({policy,children}:{policy?:boolean;children:ReactNode}){
  const [evidence,setEvidence]=useState(false);
  const cards=policy?[
    ['Punjači na poslu','Duži boravak omogućava sporije punjenje i manji večernji vrh.'],
    ['Više dostupnih mesta','Više priključenih vozila deli ograničenu snagu. Broj punjača ne povećava kapacitet mreže.'],
    ['Javni centri na SN mreži','Zasebna trafostanica može rasteretiti postojeći stambeni NN ogranak.'],
  ]:[
    ['Kod kuće · noću','Korisnik zada rok odlaska. Punjenje se raspoređuje van vrha, npr. 00–06 h, ako je to dovoljno.'],
    ['Na poslu · tokom dana','Raspodela snage tokom boravka, bez zajedničkog početka po dolasku.'],
    ['Javni i brzi punjači','Kada lokalna rezerva opada, smanjimo snagu punjenja u dozvoljenim granicama.'],
  ];
  return <div className="location-policy"><div className="mcp-demo-tabs"><button aria-pressed={!evidence} onClick={()=>setEvidence(false)}>{policy?'Predlog razvoja':'Predlog upravljanja'}</button><button aria-pressed={evidence} onClick={()=>setEvidence(true)}>Rezultati studije</button></div>
    {evidence?children:<><div className="location-cards">{cards.map(([title,body],i)=><article key={title}><small>0{i+1}</small><h2>{title}</h2><p>{body}</p></article>)}</div>
    <div className="location-takeaway">{policy?'Više izbora gde i kada punimo olakšava upravljanje i postepeno širenje.':'Raspoloživa snaga + energija do odlaska → raspored punjenja.'}</div>
    <p className="chart-note">{policy?'Predlog za novu analizu. SN priključak traži proveru i ulaganje; transformacija i uzvodna ograničenja ostaju. Postojeća studija računa sva EV na zbirnom NN nivou.':'Simulator proverava modelovane delove mreže na 15 minuta. Rezerva svakog stvarnog transformatora zahteva detaljniji model i podatke. Period 00–06 h je primer, ne fiksni start svih vozila.'}</p></>}
  </div>;
}
