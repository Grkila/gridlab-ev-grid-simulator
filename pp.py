import pandapower as pp
import pandapower.plotting as ppp
import gdf_gen
import utils as ut
import vrp
from tqdm import tqdm
import mapping

cf = ut.cf['3']['pandapower']


def find_switch_type(n, el):
    for typ in ['ss', 'st', 'sw']:
        if n in el['switches'][typ].keys():
            return typ


def populate_net(dt):
    s, sp, t, sols = (dt[typ] for typ in ['s', 'sp', 't', 'sol_gdfs'])

    def add_substations():
        # For each substation, create HV and MV buses, the external grid, and the substation as a trafo
        el['buses']['ss'] = {}
        for i, sub in tqdm(
                s.iterrows(), desc=ut.pad_center('Substations', 24),
                colour='green', unit=' sub', total=len(s)):
            for volt in ['HV', 'MV']:
                bus = {'net': net,
                       'name': f"SS Bus {i} {volt}",
                       'vn_kv': cf[f"{volt}_kV"],
                       'type': 'b',
                       'zone': 'substations',
                       'geodata': gxy[sub.name],
                       'in_service': True}
                el['buses']['ss'][f'{i}_{volt}'] = pp.create_bus(**bus)
            trf = {'net': net,
                   'hv_bus': el['buses']['ss'][f'{i}_HV'],
                   'lv_bus': el['buses']['ss'][f'{i}_MV'],
                   'name': i,  # f"Trafo {i}" # str creates issue in mapping.py
                   **cf['subst_transf_opt']}
            el['trafos'][i] = pp.create_transformer(**trf)
            xge = {'net': net,
                   'bus': el['buses']['ss'][f'{i}_HV'],
                   'name': f"ExtGrid {i}",
                   **cf['XG_opt']}
            el['xg'][i] = pp.create.create_ext_grid(**xge)

    def add_loads():
        # Create a bus, then a load for each transformer
        for n in t['sub_pair'].unique():
            el['buses'][n] = {}
            el['loads'][n] = {}
        for i, transf in tqdm(
                t.iterrows(), desc=ut.pad_center('Transformers', 24),
                colour='green', unit=' loads', total=len(t)):
            bus = {'net': net,
                   'name': f"MV Bus {i}",
                   'vn_kv': cf['MV_kV'],
                   'type': 'n',
                   'zone': 'group_' + str(transf['sub_pair']),
                   'geodata': gxy[transf.name],
                   'in_service': True}
            el['buses'][transf['sub_pair']][str(i)] = pp.create_bus(**bus)
            load = {'net': net,
                    'in_service': True,
                    'bus': el['buses'][transf['sub_pair']][str(i)],
                    'p_mw': transf['cap'],
                    'name': f"Load {i}",
                    **cf['load_opt']}
            el['loads'][transf['sub_pair']][str(i)] = pp.create_load(**load)

    def add_lines():
        el['lines']['sw'] = {}
        # Create a line element for each segment of each circuit in the solution
        line1 = {'net': net, **cf['line_opt']}
        el['lines']['ss'] = {}
        for gn, grp in tqdm(  # For each group (subst pair)
                sols.items(), desc=ut.pad_center('Lines for group', 24),
                colour='green', unit=' groups'):
            fr, to = (f'{sp.loc[gn, "ID_1"]}_MV', f'{sp.loc[gn, "ID_2"]}_MV')
            # line2 = {
            #     'in_service': False,
            #     'from_bus': el['buses']['ss'][fr],
            #     'to_bus':  el['buses']['ss'][to],
            #     'length_km': sp.loc[gn, 'rt_st_l'],
            #     'geodata': sp.loc[gn, 'rt_st'].coords,
            #     'name': f'{fr}-{to}'}
            # el['lines']['ss'][f'{fr}-{to}'] = pp.create_line(**line1, **line2)  # Auxiliary lines
            el['lines'][gn] = {}
            for rn, rte in grp.iterrows():  # For each route in the solution to the group
                el['lines'][gn][rn] = {}
                for i in range(0, len(rte['route']) - 1):
                    fr = str(rte['r_og'][i])
                    to = str(rte['r_og'][i + 1])
                    if i == 0:
                        fr += '_MV'
                        frombus = el['buses']['ss'][fr]
                        tobus = el['buses'][gn][to]
                    elif i == len(rte['route']) - 2:
                        to += '_MV'
                        frombus = el['buses'][gn][fr]
                        tobus = el['buses']['ss'][to]
                    else:
                        frombus = el['buses'][gn][fr]
                        tobus = el['buses'][gn][to]
                    line2 = {
                        'in_service': True,
                        'length_km': gdf_gen.get_planar_length(rte['geometry'].geoms[i]),
                        'geodata': list(rte['geometry'].geoms[i].coords),
                        'from_bus': frombus,
                        'to_bus': tobus,
                        'name': f'Line {i} ({fr}-{to})'}
                    nl = pp.create_line(**line1, **line2)
                    el['lines'][gn][rn][line2['name']] = nl
                    if i == int(len(rte["route"]) / 2):
                        el['lines']['sw'][line2['name']] = nl

    def add_switches():
        # Create switches: one for each line connected to each substation
        el['switches'] = {'ss': {}, 'st': {}, 'sw': {}}
        for _, trf in net.trafo.iterrows():
            bus = trf['lv_bus']
            for _, ln in net.line[(net.line['from_bus'] == bus) | (net.line['to_bus'] == bus)].iterrows():
                n = ln['name'].replace(f'{trf["name"]}', f'{trf["name"]}_S')
                ns = pp.create.create_switch(
                    net=net,
                    bus=bus,
                    element=ln.name,
                    et='l',
                    type='DS',
                    name=n,
                    closed=n.count('MV') < 2)
                typ = 'ss' if (ln['from_bus'] in (el['buses']['ss'].values()) and
                               ln['to_bus'] in (el['buses']['ss'].values())) else 'st'
                el['switches'][typ][n] = ns
        # One in the middle of each route
        for sw in el['lines']['sw'].values():
            line = net.line.loc[sw]
            el['switches']['sw'][line['name']] = pp.create.create_switch(
                net,
                line['from_bus'],
                sw,
                et='l',
                type='DS',
                name=line['name'])

    print('The network is being created. Now adding:')
    G = dt['G']
    gxy = vrp.xy_from_graph(G)
    net = pp.create_empty_network()
    el = {'buses': {}, 'trafos': {}, 'xg': {}, 'lines': {}, 'loads': {}, 'switches': {}}
    add_substations()
    add_loads()
    add_lines()
    add_switches()

    return net, el


# @ut.runtime_counter('Calculating network power flows')
def run_net(net):
    ppp.runpp(net)
    return net


if __name__ == "__main__":
    data = ut.data_un('data.pkl')
    ppnet = populate_net(data)
    pprun = run_net(ppnet['net0'])
    mapping.pp_network(data[2]['poly'].centroid, pprun).save('scenario.html')
