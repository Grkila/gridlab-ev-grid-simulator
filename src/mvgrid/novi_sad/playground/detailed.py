"""Explicit, selected-snapshot detailed validation; never runs on ordinary cases."""
from __future__ import annotations
import math
import time
import pandapower as pp
from pandapower.powerflow import LoadflowNotConverged
from mvgrid.paths import NOVI_SAD_MODEL_DIR


def detailed_check(result, steps):
    """Replay exact block dispatch into detailed member loads; hubs use source MV bus."""
    net=pp.from_json(str(NOVI_SAD_MODEL_DIR/'ppnet_novi_sad.json'))
    if result.get('operating_scenario'):
        net.ext_grid.vm_pu=result['operating_scenario']['source_voltage_pu']
    if result.get('capacity_alignment'):
        from .rebalance import rebalance_sources
        from .capacity_alignment import align_delivery_capacity
        excluded=result['capacity_alignment'].get('excluded_sources',[])
        rebalance_sources(net,excluded)
        align_delivery_capacity(net, result['capacity_alignment']['estimate'],excluded_sources=excluded)
    indices={str(row.synthetic_id):int(i) for i,row in net.load.iterrows()}
    original=net.load.p_mw.copy()
    net.load.loc[:,['p_mw','q_mvar']]=0.0
    blocks={b['id']:b for b in result['blocks']}
    active_sources={b['source_id'] for b in result['blocks']}
    for index,row in net.ext_grid.iterrows():
        if str(net.bus.at[int(row.bus),'zone']) not in active_sources:
            net.ext_grid.at[index,'in_service']=False
    hub_loads={}
    for b in result['blocks']:
        if b.get('kind')=='public_hub':
            candidates=net.load[net.load.primary_station_id==b['source_id']]
            if candidates.empty: raise ValueError('No detailed source mapping')
            # Explicit proxy connection: source LV side of highest-voltage transformer.
            station_trafos=net.trafo[net.trafo.station_id==b.get('delivery_id',b['source_id'])]
            trafo=station_trafos.sort_values('vn_hv_kv',ascending=False).iloc[0]
            hub_loads[b['id']]=pp.create_load(net,int(trafo.lv_bus),p_mw=0,q_mvar=0,name=b['id'])
    output=[]
    for step in steps:
        interval=result['intervals'][step]
        for snapshot in interval['blocks']:
            block=blocks[snapshot['id']]
            members=[indices[x] for x in block['member_ids']]
            if members:
                weights=original.loc[members]/original.loc[members].sum()
                for index,weight in weights.items():
                    p=snapshot['total_kw']/1000*weight
                    net.load.loc[index,['p_mw','q_mvar']]=[p,p*math.tan(math.acos(.97))]
            else:
                p=snapshot['total_kw']/1000
                net.load.loc[hub_loads[block['id']],['p_mw','q_mvar']]=[p,p*math.tan(math.acos(.97))]
        started=time.perf_counter()
        try:
            pp.runpp(net,numba=False,max_iteration=40)
            detailed=dict(converged=True,min_voltage_pu=float(net.res_bus.vm_pu.min()),max_line_loading_percent=float(net.res_line.loading_percent.max()),max_transformer_loading_percent=float(net.res_trafo.loading_percent.max()),losses_kw=float((net.res_line.pl_mw.sum()+net.res_trafo.pl_mw.sum())*1000))
        except LoadflowNotConverged:
            detailed=dict(converged=False)
        delta={key:detailed[key]-interval[key] for key in ('min_voltage_pu','max_line_loading_percent','max_transformer_loading_percent','losses_kw') if detailed.get(key) is not None and interval.get(key) is not None}
        output.append(dict(step=step,detailed=detailed,reduced={k:interval.get(k) for k in detailed},detailed_minus_reduced=delta,runtime_seconds=time.perf_counter()-started))
    return dict(snapshots=output,assumptions=['Block charging distributed by member baseline demand shares.','Dedicated illustrative hubs attached to delivery transformer LV bus; excluded source loads zeroed.','Selected snapshots only; no full-year electrical feasibility claim.'])
