import {useState,type ReactNode} from 'react';

export function LocationPolicy({policy,children}:{policy?:boolean;children:ReactNode}){
  const [evidence,setEvidence]=useState(false);
  const cards=policy?[
    ['Punjači na poslu','Procena za jun: oko 18% više energetskog prostora od 08–16 h nego od 16–24 h.'],
    ['Više dostupnih mesta','Više priključenih vozila deli ograničenu snagu. Broj punjača ne povećava kapacitet mreže.'],
    ['Javni centri na SN mreži','Zaseban SN priključak sa svojom trafostanicom oslobađa postojeći stambeni NN ogranak od tog punjenja.'],
  ]:[
    ['Kod kuće · noću','Korisnik zada rok odlaska. Punjenje se raspoređuje van vrha, npr. 00–06 h, ako je to dovoljno.'],
    ['Na poslu · tokom dana','Raspodelimo punjenje tokom boravka. U junskom profilu ima više prostora nego uveče.'],
    ['Javni i brzi punjači','Kada lokalna rezerva opada, smanjimo snagu punjenja u dozvoljenim granicama.'],
  ];
  return <div className="location-policy"><div className="mcp-demo-tabs"><button aria-pressed={!evidence} onClick={()=>setEvidence(false)}>{policy?'Predlog razvoja':'Predlog upravljanja'}</button><button aria-pressed={evidence} onClick={()=>setEvidence(true)}>{policy?'Rezultati studije':'Procena iz krive'}</button></div>
    {evidence?children:<><div className="location-cards">{cards.map(([title,body],i)=><article key={title}><small>0{i+1}</small><h2>{title}</h2><p>{body}</p></article>)}</div>
    <div className="location-takeaway">{policy?'Više izbora gde i kada punimo olakšava upravljanje i postepeno širenje.':'Raspoloživa snaga + energija do odlaska → raspored punjenja.'}</div>
    <p className="chart-note">{policy?'Procena, ne potvrđen kapacitet. Dobit SN priključka zavisi od nove trafostanice i uzvodne mreže; priključak zahteva ulaganje. Više punjača pomaže uz zajedničko ograničenje snage.':'Simulator proverava modelovane delove mreže na 15 minuta. Rezerva svakog stvarnog transformatora zahteva detaljniji model i podatke. Period 00–06 h je primer, ne fiksni start svih vozila.'}</p></>}
  </div>;
}
