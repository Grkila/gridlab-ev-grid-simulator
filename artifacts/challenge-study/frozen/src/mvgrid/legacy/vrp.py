from . import utils as ut
import itertools as it
import networkx as nx
import vrpy
import osmnx as ox
import pandas as pd
import shapely as shp
import geopandas as gpd
import sys
from tqdm import tqdm
from time import sleep


def complement_sols(data):
    G, sol_p, sp = (data[typ] for typ in ['G', 'sol_p', 'sp'])
    gxy = xy_from_graph(G)
    sol_gdfs = {}
    for gid, gsols in tqdm(sol_p.items(), desc='Creating route Geodataframes for group', colour='green',
                           unit='groups'):
        src = sp.at[gid, 'ID_1']
        snk = sp.at[gid, 'ID_2']
        gsols['load'] = gsols['load'] / 1000
        gsols['r_og'] = [[src] + sol['route'][1:-1] + [snk] for _, sol in gsols.iterrows()]
        gsols['tr_ct'] = gsols['r_og'].apply(lambda x: len(x) - 2)
        gsols['geometry'] = [
            shp.MultiLineString([
                shp.LineString([gxy[node] for node in path])
                for path in ox.routing.shortest_path(G, [src] + ids, ids + [snk], weight='length')])
            for ids in gsols['route'].apply(lambda x: x[1:-1])]
        sol_gdfs[gid] = gpd.GeoDataFrame(gsols, geometry='geometry', crs="WGS84")
        data.update({'sol_gdfs': sol_gdfs})
    return data


def xy_from_graph(graph):
    gx = nx.get_node_attributes(graph, 'x')
    gy = nx.get_node_attributes(graph, 'y')
    return {node: (gx[node], gy[node]) for node in gx.keys()}


def create_digraphs(data):
    msg = {'src': ut.pad_center('From source', 24),
           'snk': ut.pad_center('To sink', 24),
           'nns': ut.pad_center('Transformers', 24)}
    gtg = {}
    G = data['G'].copy()
    t, sp = (data[typ].copy() for typ in ['t', 'sp'])
    for grp_id, grp in t.groupby('sub_pair'):
        print(f'\nCalculating edge distances for group: {grp_id}')
        src, snk = [sp.at[grp_id, col] for col in ['ID_1', 'ID_2']]
        ids = grp.index.tolist()
        ns_d = {node: int(t.loc[node, 'cap'] * 1000) for node in ids}
        cb_src = [(src, b) for b in ids]
        cb_snk = [(a, snk) for a in ids]
        sleep(0.1)
        cbd_src = [('Source', b, {'cost': nx.shortest_path_length(G, source=a, target=b, weight='length') / 1000})
                   for (a, b) in tqdm(cb_src, desc=msg['src'], unit=' edges', colour='green')]
        cbd_snk = [(a, 'Sink', {'cost': nx.shortest_path_length(G, source=a, target=b, weight='length') / 1000})
                   for (a, b) in tqdm(cb_snk, desc=msg['snk'], unit=' edges', colour='green')]
        cb_n = list(it.combinations(ids, 2))
        cbd_n = [(a, b, {'cost': nx.shortest_path_length(G, source=a, target=b, weight='length') / 1000})
                 for (a, b) in tqdm(cb_n, desc=msg['nns'], unit=' edges', colour='green')]
        cbd_nr = [(b, a, cost) for a, b, cost in cbd_n]
        cbd_all = cbd_src + cbd_snk + cbd_n + cbd_nr
        grp_g = nx.from_edgelist(cbd_all, create_using=nx.DiGraph)
        nx.set_node_attributes(grp_g, ns_d, name='demand')
        gtg[grp_id] = grp_g
        data.update({'gr_p': gtg})
    return data


def solve_vrpy(data):
    graphs = data['gr_p']
    opts = ut.cf['2']['vrpy_opts']
    vrpy_sols = {}
    for grp_id, graph in graphs.items():
        prob = vrpy.VehicleRoutingProblem(graph, **opts['prob'])
        prob.solve(**opts['solve'])
        if prob.masterproblem.dropped_nodes:
            print(f'Nodes were dropped while VRpy was solving for group {grp_id}. Stopping process')
            sys.exit(1)
        p_l = []
        for rte_id, rte in prob.best_routes.items():
            p_l.append({'route': rte, 'length': prob.best_routes_cost[rte_id], 'load': prob.best_routes_load[rte_id]})
        vrpy_sols[grp_id] = pd.DataFrame(p_l, index=prob.best_routes.keys())
        data.update({'sol_p': vrpy_sols})
    return data
