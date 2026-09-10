"""Electrical-hierarchy reduction of the synthetic reference, never geographic clustering."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import defaultdict
import networkx as nx
import pandapower as pp
from mvgrid.paths import DATA_DIR, NOVI_SAD_GENERATED_DIR, NOVI_SAD_MODEL_DIR

REDUCED_PATH=DATA_DIR/'novi_sad'/'playground'/'reduced_network.json'


def build_network():
    if not REDUCED_PATH.exists():
        raise FileNotFoundError('Run scripts/build_playground_network.py to generate the electrical reduction')
    net=pp.from_json(str(REDUCED_PATH))
    return net,net['playground_blocks']


def reduce_reference(target_blocks=4, excluded_sources=('NS1','NS6','FUT'), excluded_hubs=('NS1','NS6','FUT')):
    """Collapse load-bearing feeder subtrees, preserving every station transformer/link."""
    reference=NOVI_SAD_MODEL_DIR/'ppnet_novi_sad.json'
    full=pp.from_json(str(reference))
    from .rebalance import rebalance_sources
    reassignments=rebalance_sources(full,excluded_sources)
    from .capacity_alignment import align_delivery_capacity
    alignment=align_delivery_capacity(full,excluded_sources=excluded_sources)
    alignment['demand_reassignment']={'method':'Largest feeder branches assigned first to the remaining 20-kV source with lowest projected demand/original-MVA ratio; original feeder impedances retained as planning equivalents.','branches':reassignments}
    alignment['boundary']='MV AC power flow with aggregate transmission and downstream capacity constraints'
    alignment['operating_model']={
        'version': 2, 'reserve_fraction': alignment['estimate']['reported_reserve_fraction'],
        'transformer_interpretation': 'The unspecified 150 MW is assigned to an aggregate downstream MV/LV stage for this scenario; not a verified asset inventory.',
        'reserve_interpretation': 'The last 25% of each rating is usable reserve. Show reserve use above 75%; enforce the full 100% rating.',
        'lv_allocation': 'Editable fractions of baseline and EV demand; defaults 0.5 and 1.0 are assumptions, not supplied measurements.',
        'electrical_boundary': 'Transmission and downstream LV stages are aggregate kW constraints, not additional AC assets. MV power flow accounts for each load once.'}
    with (NOVI_SAD_GENERATED_DIR/'novi_sad_synthetic_transformers.csv').open(encoding='utf-8') as f:
        inventory={r['synthetic_id']:r for r in csv.DictReader(f)}
    active_loads=full.load[~full.load.primary_station_id.isin(excluded_sources)]
    active_stations=set(active_loads.primary_station_id)|set(active_loads.delivery_station_id)
    net=pp.create_empty_network(name='Novi Sad electrical-hierarchy reduced synthetic proxy')
    busmap={}
    def bus(old):
        old=int(old)
        if old not in busmap:
            row=full.bus.loc[old]
            coords=full.bus_geodata.loc[old,['x','y']].tolist() if old in full.bus_geodata.index else None
            busmap[old]=pp.create_bus(net,vn_kv=float(row.vn_kv),name=str(row['name']),zone=row.zone,geodata=coords)
        return int(busmap[old])
    trafomap={}
    for i,r in full.trafo.iterrows():
        if r.station_id not in active_stations: continue
        trafomap[int(i)]=pp.create_transformer_from_parameters(net,bus(r.hv_bus),bus(r.lv_bus),sn_mva=r.sn_mva,vn_hv_kv=r.vn_hv_kv,vn_lv_kv=r.vn_lv_kv,vk_percent=r.vk_percent,vkr_percent=r.vkr_percent,pfe_kw=r.pfe_kw,i0_percent=r.i0_percent,shift_degree=r.shift_degree,name=r['name'])
        net.trafo.loc[trafomap[int(i)],'station_id']=r.station_id
    for _,r in full.ext_grid.iterrows():
        if str(full.bus.at[int(r.bus),'zone']) in active_stations: pp.create_ext_grid(net,bus(r.bus),vm_pu=r.vm_pu,name=r['name'])
    graph=nx.Graph()
    line_map={}
    for i,r in full.line.iterrows():
        graph.add_edge(int(r.from_bus),int(r.to_bus),kind='line',index=int(i))
        if r.path_kind=='legacy_35kv_inferred_route':
            line_map[int(i)]=pp.create_line_from_parameters(net,bus(r.from_bus),bus(r.to_bus),length_km=r.length_km,r_ohm_per_km=r.r_ohm_per_km,x_ohm_per_km=r.x_ohm_per_km,c_nf_per_km=r.c_nf_per_km,max_i_ka=r.max_i_ka,parallel=int(r.parallel),name=r['name'])
    for i,r in full.trafo.iterrows(): graph.add_edge(int(r.hv_bus),int(r.lv_bus),kind='trafo',index=int(i))
    total=float(active_loads.p_mw.sum())
    retained_fraction=total/float(full.load.p_mw.sum())
    blocks=[]
    # Group by delivery before subdividing radial feeder connectivity.
    for delivery,loads in active_loads.groupby('delivery_station_id',sort=True):
        delivery_trafo=full.trafo[full.trafo.station_id==delivery].iloc[0]
        delivery_index=int(delivery_trafo.name)
        root=int(delivery_trafo.lv_bus)
        source=str(loads.iloc[0].primary_station_id)
        source_trafo=full.trafo[full.trafo.station_id==source].iloc[0]
        source_root=int(source_trafo.hv_bus)
        paths={int(i):nx.shortest_path(graph,root,int(r.bus)) for i,r in loads.iterrows()}
        groups=[list(paths)]
        def split(members):
            prefix=0
            while all(len(paths[i])>prefix for i in members) and len({paths[i][prefix] for i in members})==1: prefix+=1
            children=defaultdict(list)
            for i in members: children[paths[i][prefix] if len(paths[i])>prefix else ('at',i)].append(i)
            return list(children.values())
        while len(groups)<target_blocks:
            candidates=[(float(full.load.loc[g,'p_mw'].sum()),index,split(g)) for index,g in enumerate(groups) if len(g)>1]
            candidates=[c for c in candidates if len(c[2])>1]
            if not candidates: break
            _,index,parts=max(candidates,key=lambda c:(c[0],-c[1]))
            groups[index:index+1]=parts
        upstream=nx.shortest_path(graph,source_root,root)
        upstream_lines=[]; upstream_trafos=[]
        for a,b in zip(upstream,upstream[1:]):
            edge=graph[a][b]
            (upstream_lines if edge['kind']=='line' else upstream_trafos).append((line_map if edge['kind']=='line' else trafomap)[edge['index']])
        def make_block(members,number,hub=False):
            p=float(full.load.loc[members,'p_mw'].sum()) if members else 0.
            block_id=f'{delivery}-HUB' if hub else f'{delivery}-F{number}'
            member_ids=[str(full.load.at[i,'synthetic_id']) for i in members]
            coords=full.bus_geodata.loc[root]
            lat=sum(float(inventory[x]['latitude'])*float(full.load.at[i,'p_mw']) for i,x in zip(members,member_ids))/p if p else float(coords.y)
            lon=sum(float(inventory[x]['longitude'])*float(full.load.at[i,'p_mw']) for i,x in zip(members,member_ids))/p if p else float(coords.x)
            resistance=reactance=0.
            edge_power=defaultdict(float)
            for i in members:
                for a,b in zip(paths[i],paths[i][1:]):
                    edge=graph[a][b]
                    r=full.line.loc[edge['index']]
                    weight=float(full.load.at[i,'p_mw'])/p
                    resistance+=weight*r.length_km*r.r_ohm_per_km/r.parallel
                    reactance+=weight*r.length_km*r.x_ohm_per_km/r.parallel
                    edge_power[edge['index']]+=float(full.load.at[i,'p_mw'])
            voltage=float(full.bus.at[root,'vn_kv'])
            capacity=1000. if hub else min(math.sqrt(3)*voltage*float(full.line.at[e,'max_i_ka'])*float(full.line.at[e,'parallel'])*.97*1000*p/downstream for e,downstream in edge_power.items())
            blockbus=pp.create_bus(net,vn_kv=voltage,name=block_id,geodata=(lon,lat))
            line=pp.create_line_from_parameters(net,bus(root),blockbus,length_km=1.,r_ohm_per_km=max(.001,resistance),x_ohm_per_km=max(.001,reactance),c_nf_per_km=0,max_i_ka=capacity/(1000*math.sqrt(3)*voltage*.97),name=block_id)
            load=pp.create_load(net,blockbus,p_mw=p,q_mvar=p*math.tan(math.acos(.97)),name=block_id)
            mixture=defaultdict(float)
            for i,x in zip(members,member_ids):
                land=inventory[x]['land_use']; kind='industrial' if land in ('industrial','military') else 'commercial' if land in ('commercial','retail') else 'residential'
                mixture[kind]+=float(full.load.at[i,'p_mw'])/p
            sourcecoords=full.bus_geodata.loc[source_root]
            blocks.append(dict(id=block_id,source_id=source,delivery_id=str(delivery),delivery_station_id=str(delivery),lat=lat,lon=lon,source_lat=float(sourcecoords.y),source_lon=float(sourcecoords.x),delivery_lat=float(coords.y),delivery_lon=float(coords.x),delivery_voltage_kv=voltage,source_bus_index=bus(source_root),delivery_bus_index=bus(root),retained_demand_fraction=retained_fraction,upstream_bus_indices=[bus(x) for x in upstream],upstream_line_indices=[int(x) for x in upstream_lines],upstream_trafo_indices=[int(x) for x in upstream_trafos],base_weight=p/total,base_kw=p*1000,capacity_kw=capacity,source_capacity_kw=float(source_trafo.sn_mva)*.97*1000,delivery_capacity_kw=float(delivery_trafo.sn_mva)*.97*1000,load_index=int(load),bus_index=int(blockbus),line_index=int(line),trafo_index=int(trafomap[delivery_index]),path_line_indices=[int(x) for x in upstream_lines]+[int(line)],path_trafo_indices=[int(x) for x in upstream_trafos],path_bus_indices=[bus(x) for x in upstream]+[int(blockbus)],mixture={'public':1.} if hub else dict(mixture),member_ids=member_ids,kind='public_hub' if hub else 'electrical_subtree',assumptions=['Partitions follow synthetic reference delivery and radial feeder branching, not geography.','Demand-weighted path R/X and bottleneck/fraction thermal equivalent; shared feeder coupling within delivery is approximated.','Shunt capacitance omitted on equivalent feeder.']+(['Illustrative1MW charging hub at delivery station; not observed infrastructure.'] if hub else [])))
        for number,members in enumerate(groups,1): make_block(members,number)
        if str(delivery) not in excluded_hubs:
            make_block([],0,True)
    net['playground_blocks']=blocks
    net['capacity_alignment']=alignment
    for block in blocks:
        block['district_planning_factor']=1.
        block['capacity_provenance']=alignment['estimate']['source']+' MV delivery equivalents allocated by original station MVA; full rating is usable, with the last 25% reported as reserve.'
    net['playground_assumptions']=['Synthetic electrical hierarchy, not as-built.','All reference station transformers and35kV interstation links retained.','Equivalent subtree feeder approximation is not an exact network reduction.']
    net['playground_assumptions'][1]='Removed NS1, NS6 and FUT supplies; reassigned their complete demand to retained 20-kV feeder equivalents. Interstation 35-kV links retained.'
    net['retained_demand_fraction']=retained_fraction
    net['excluded_sources']=list(excluded_sources)
    net['excluded_hubs']=[f'{station}-HUB' for station in excluded_hubs]
    net['reference_sha256']=hashlib.sha256(reference.read_bytes()).hexdigest()
    net['hierarchy_nodes']=[dict(id=int(i),name=str(r['name']),vn_kv=float(r.vn_kv),lon=float(net.bus_geodata.at[i,'x']),lat=float(net.bus_geodata.at[i,'y'])) for i,r in net.bus.iterrows()]
    net['hierarchy_edges']=[dict(kind=kind,index=int(i),from_bus=int(r[a]),to_bus=int(r[b])) for kind,table,a,b in [('line',net.line,'from_bus','to_bus'),('transformer',net.trafo,'hv_bus','lv_bus')] for i,r in table.iterrows()]
    return net,blocks
