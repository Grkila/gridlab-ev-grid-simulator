import {Building2, House, Factory, Car, Zap, RadioTower} from 'lucide-react';
import './control-diagram.css';

export function ControlDiagram(){
  return <div className="control-diagram">
    <div className="control-blocks">
      <div className="control-inputs"><span className="control-kicker">INPUTS</span><h2>Grid and vehicles</h2><p>Transformer loading · available power</p><p>Connection · voltage and loading limits</p><p>Remaining energy · departure deadline</p><p>Charger power · charging efficiency</p></div>
      <div className="control-connector"><span>data</span><b>→</b></div>
      <div className="control-core"><span className="control-kicker">CENTRAL CONTROLLER</span><h2>Capacity-aware</h2><p>1. Calculate available power</p><p>2. Prioritize earlier departures</p><p>3. Check the grid and adjust power</p><small>Simulation: recalculate every 15 minutes</small></div>
      <div className="control-connector"><span>commands</span><b>→</b></div>
      <div className="control-outputs"><span className="control-kicker">OUTPUTS</span><h2>Charging power</h2><p>Permitted power per charger or node</p><p>Charge · reduce power · wait</p><p>Updated allocation for the next step</p></div>
    </div>
    <div className="control-city">
      <svg className="control-wires" viewBox="0 0 1400 230" preserveAspectRatio="none" aria-hidden="true">
        <defs><marker id="control-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6" fill="none" stroke="#d4f59d"/></marker></defs>
        <path className="power-wire" d="M150 130 H1300 M570 130 V165 M910 130 V165 M1250 130 V165"/>
        <path className="data-wire" d="M150 92 V35 H700 V0"/>
        <path className="command-wire" d="M740 0 V60 H1250 V160 M740 60 H570 V160 M910 60 V160" markerEnd="url(#control-arrow)"/>
      </svg>
      <div className="control-feedback">Measurements and remaining energy return to the controller</div>
      <div className="control-station"><RadioTower size={45}/><strong>Substation</strong><small>Loading + reserve</small></div>
      <div className="control-districts">{[{name:'Residential block',Icon:House},{name:'Workplace district',Icon:Building2},{name:'Public parking',Icon:Factory}].map(({name,Icon})=><div className="control-district" key={name}><div className="control-buildings"><Icon size={54}/><Icon size={36}/></div><strong>{name}</strong><div className="control-charger"><Zap size={22}/><Car size={36}/><span>requested P (kW)</span></div></div>)}</div>
    </div>
    <div className="control-legend"><span><i/> Electrical connection</span><span><i/> Measurements</span><span><i/> Power commands</span><small>Target architecture. Live telemetry and charger communication require integration.</small></div>
  </div>;
}
