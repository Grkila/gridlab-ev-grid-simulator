import {Building2, House, Factory, Car, Zap, RadioTower} from 'lucide-react';
import './control-diagram.css';

export function ControlDiagram(){
  return <div className="control-diagram">
    <div className="control-blocks">
      <div className="control-inputs"><span className="control-kicker">ULAZI</span><h2>Mreža i vozila</h2><p>Opterećenje trafoa · raspoloživa snaga</p><p>Priključak · granice napona i opterećenja</p><p>Preostala energija · rok odlaska</p><p>Snaga punjača · efikasnost punjenja</p></div>
      <div className="control-connector"><span>podaci</span><b>→</b></div>
      <div className="control-core"><span className="control-kicker">CENTRALNI KONTROLER</span><h2>Capacity-aware</h2><p>1. Izračuna slobodnu snagu</p><p>2. Daje prioritet bližem odlasku</p><p>3. Proverava mrežu i koriguje snagu</p><small>U simulaciji: novi proračun na 15 min</small></div>
      <div className="control-connector"><span>komande</span><b>→</b></div>
      <div className="control-outputs"><span className="control-kicker">IZLAZI</span><h2>Snaga punjenja</h2><p>Dozvoljena snaga po punjaču / čvoru</p><p>Puni · smanji snagu · sačekaj</p><p>Ažurirana raspodela za sledeći korak</p></div>
    </div>
    <div className="control-city">
      <svg className="control-wires" viewBox="0 0 1400 230" preserveAspectRatio="none" aria-hidden="true">
        <defs><marker id="control-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="none" stroke="#d4f59d"/></marker></defs>
        <path className="power-wire" d="M150 130 H1300 M570 130 V165 M910 130 V165 M1250 130 V165"/>
        <path className="data-wire" d="M150 92 V35 H700 V0"/>
        <path className="command-wire" d="M740 0 V60 H1250 V160 M740 60 H570 V160 M910 60 V160" markerEnd="url(#control-arrow)"/>
      </svg>
      <div className="control-feedback">Merenja i preostala energija se vraćaju kontroleru</div>
      <div className="control-station"><RadioTower size={45}/><strong>Trafostanica</strong><small>Opterećenje + rezerva</small></div>
      <div className="control-districts">{[{name:'Stambeni blok',Icon:House},{name:'Poslovna zona',Icon:Building2},{name:'Javni parking',Icon:Factory}].map(({name,Icon})=><div className="control-district" key={name}><div className="control-buildings"><Icon size={54}/><Icon size={36}/></div><strong>{name}</strong><div className="control-charger"><Zap size={22}/><Car size={36}/><span>zadato P (kW)</span></div></div>)}</div>
    </div>
    <div className="control-legend"><span><i/> Električna veza</span><span><i/> Merenja</span><span><i/> Komande snage</span><small>Skica ciljne primene: stvarna telemetrija i veza sa punjačima zahtevaju integraciju.</small></div>
  </div>;
}
