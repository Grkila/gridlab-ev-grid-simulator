"""Reassign removed 20-kV source feeder branches without dropping city demand."""
import networkx as nx


def rebalance_sources(net, excluded_sources):
    excluded=set(excluded_sources)
    if not excluded:
        return []
    stations=net.trafo.set_index('station_id',drop=False)
    if any(float(stations.loc[s,'vn_lv_kv']) != 20 for s in excluded):
        raise ValueError('Source rebalancing currently supports 20-kV source removal only')
    targets=sorted(str(s) for s,r in stations.iterrows() if r.vn_lv_kv==20 and s not in excluded)
    if not targets:
        raise ValueError('At least one 20-kV source must remain')
    graph=nx.Graph()
    for index,line in net.line.iterrows():
        graph.add_edge(int(line.from_bus),int(line.to_bus),index=int(index))
    demand={s:float(net.load.loc[net.load.primary_station_id==s,'p_mw'].sum()) for s in targets}
    branches=[]
    for source in sorted(excluded):
        root=int(stations.loc[source,'lv_bus'])
        tree=graph.subgraph(nx.node_connected_component(graph,root)).copy()
        edges=[(neighbor,tree[root][neighbor]['index']) for neighbor in tree.neighbors(root)]
        tree.remove_node(root)
        source_loads=net.load[net.load.primary_station_id==source]
        for neighbor,index in edges:
            buses=nx.node_connected_component(tree,neighbor)
            members=list(source_loads.index[source_loads.bus.isin(buses)])
            if members:
                branches.append((float(net.load.loc[members,'p_mw'].sum()),source,root,index,members))
        direct=list(source_loads.index[source_loads.bus==root])
        if direct:
            branches.append((float(net.load.loc[direct,'p_mw'].sum()),source,root,None,direct))
    records=[]
    for mw,source,root,index,members in sorted(branches,key=lambda r:(-r[0],r[1],-1 if r[3] is None else r[3])):
        target=min(targets,key=lambda s:((demand[s]+mw)/float(stations.loc[s,'sn_mva']),s))
        target_root=int(stations.loc[target,'lv_bus'])
        if index is None:
            net.load.loc[members,'bus']=target_root
        else:
            endpoint='from_bus' if int(net.line.at[index,'from_bus'])==root else 'to_bus'
            net.line.at[index,endpoint]=target_root
        net.load.loc[members,['primary_station_id','delivery_station_id']]=[target,target]
        demand[target]+=mw
        records.append(dict(original_source=source,source_id=target,reference_line_index=index,
                            demand_mw=mw,member_ids=[str(net.load.at[i,'synthetic_id']) for i in members]))
    if net.load.primary_station_id.isin(excluded).any():
        raise ValueError('Source reassignment did not cover every removed-source load')
    net.trafo.loc[net.trafo.station_id.isin(excluded),'in_service']=False
    for i,row in net.ext_grid.iterrows():
        if str(net.bus.at[int(row.bus),'zone']) in excluded:
            net.ext_grid.at[i,'in_service']=False
    return records
