import pandas as pd
import geopandas as gpd
import osmnx as ox
import shapely as shp
import shapely.geometry as shpg
import osm
import gdf_gen
import vrp
import utils as ut


def create_gdfs(data):
    # region Define local constants
    poly = osm.get_cities_polygon()
    trbyc, ctrcap = (ut.cf['1'][par] for par in ['add_transf_by_coord', 'custom_transf_cap'])
    crs, afs, trc, p2m, od = (
        ut.cf['3'][par] for par in
        ['crs', 'area_factors', 'std_transfo_capacity', 'peak_to_mean_ratio', 'overdesign_factor']
    )
    # endregion

    # region Nested functions
    def add_t(t_d):
        manual_t = pd.DataFrame.from_dict(t_d, orient='index')
        manual_t.index.name = 'ID'
        manual_t = gpd.GeoDataFrame(manual_t, geometry='geometry', crs=crs)
        return pd.concat([t, manual_t], ignore_index=False)

    def create_sub_pairs_gdf(sgdf):
        sx = sgdf.copy().explode('pairs').reset_index(drop=False)
        s_p = sx.merge(sx, on='pairs', suffixes=('_1', '_2'))
        s_p = s_p.query('ID_1 != ID_2').drop_duplicates(subset=['pairs']).set_index('pairs', drop=True)
        return s_p
    # endregion
    queries = ut.cf['1']['queries']

    # for name, gdf in zip(queries, [osm.gdf_from_osm(typ, poly) for typ in queries.keys()]):
    #     globals()[name] = gdf

    t, s, sc, lu, ch, d = (osm.gdf_from_osm(typ, poly) for typ in ['t', 's', 'sc', 'lu', 'ch', 'd'])  # GDFs Overpass

    # region Process transformer dataframe
    t = t[~t.index.isin(s.index)]  # Remove substations
    gdf_gen.gdf_deduplicate(t)  # Eliminate internal duplicates
    t['cap'] = trc  # Set default transformer capacity
    m_t_d = {10000 + n + 1: {
        'type': 'm',
        'tag': '',
        'name': f'Manual trafo {n + 1}',
        'geometry': shpg.Point([tr[0][1], tr[0][0]]),
        'cap': (tr[1] if tr[1] else trc)}
        for n, tr in enumerate(trbyc)}
    t = add_t(m_t_d) if m_t_d else t  # Add manual transformers
    t.loc[ctrcap.keys(), 'cap'] = ctrcap.values()  # Set custom transformer capacities
    # endregion
    sp = create_sub_pairs_gdf(s)  # Substation pairs
    data = {'poly': poly, 's': s, 'sc': sc, 't': t, 'lu': lu, 'ch': ch, 'sp': sp, 'd': d}
    return data


def extend_gdf_data(data):
    poly = data['poly']
    ch, lu, sc, t, d = (data[typ].copy() for typ in ['ch', 'lu', 'sc', 't', 'd'])
    crs, afs, trc, p2m, od = (
        ut.cf['3'][par] for par in
        ['crs', 'area_factors', 'std_transfo_capacity', 'peak_to_mean_ratio', 'overdesign_factor']
    )

    # region Nested Functions
    def cleanup_ch(ch0):
        def cap_st_to_int(cap):
            if isinstance(cap, int):
                return cap
            elif isinstance(cap, str) and len(cap) > 0:
                word1 = cap.split()[0]
                if word1.isdigit():
                    return int(word1)
            return 1
        ch['tag'] = ch['tag'].apply(cap_st_to_int)
        ch['dem'] = ch['tag'] * afs['evcharger'] * od
        return ch
    
    def cleanup_lu(lu0):
        lu0 = lu0.loc[lu0['geometry'].geom_type == 'Polygon'].copy()  # Keep only landuse polygons
        gdf_gen.gdf_deduplicate(lu0)  # Eliminate internal duplicated areas
        lu0 = lu0[~lu0.index.isin(sc.index)]  # Remove geometries that are going to be added later as special consumers
        lu0sc = lu0.sjoin(sc, predicate='intersects')
        lu0['geometry'] = lu0.apply(lambda r:
                                  r['geometry'].difference(lu0sc.loc[r.name]['geometry']) if r.name in lu0sc.index
                                  else r['geometry'], axis=1)  # Subtract special consumer areas
        lu0 = lu0[~lu0['geometry'].is_empty]  # Remove rows where the entire geometry is within a special consumer
        lu0['area'] = lu0['geometry'].apply(gdf_gen.get_planar_area) * 100
        lu0['dem'] = lu0.apply(lambda r: r['area'] * afs.get(r['tag']), axis=1) * p2m * od
        if not sc.empty:
            sc['area'] = sc['geometry'].apply(gdf_gen.get_planar_area) * 100
        lu0 = pd.concat([lu0, sc], axis=0)  # Add special consumers
        return lu0

    def voronoi_around_t(t0):
        tr = t0.copy()
        tr['geometry'] = tr['geometry'].apply(lambda x: x.centroid)
        voronoi = shp.voronoi_polygons(tr.geometry.unary_union, extend_to=poly)
        v0 = (gpd.GeoDataFrame(geometry=list(voronoi.geoms), crs=crs)
             .sjoin(tr, how='inner', predicate='contains'))
        v0 = gpd.overlay(
            v0,
            gpd.GeoDataFrame([poly], geometry=0, crs="WGS84"),
            how='intersection'
        ).set_index('index_right')
        v0['name'] = v0.index
        return v0[['geometry', 'name', 'cap']]

    def transf_within_districts(d_gdf, t_gdf):
        dist = d_gdf.copy()
        t_gdf.sindex
        # dist['ts'] = dist.apply(lambda r: [
        #     t_gdf.index[idx] for idx in t_gdf.sindex.query(r['geometry'], predicate='contains')
        # ], axis=1)
        dist['cap'] = dist.apply(
            lambda r: sum(t_gdf.iloc[idx]['cap'] for idx in t_gdf.sindex.query(r['geometry'], predicate='contains')),
            axis=1)
        return dist[['geometry', 'name', 'cap']]


        tv['geometry'] = v['geometry']

        tvlu = gdf_gen.gdfs_intersection(tv, lu)
        tvlu = tvlu.rename(columns={'tag_r': 'lu', 'area': 'a_lu', 'dem': 'dem_lu'})
        tvlu['a_luv'] = tvlu['geometry'].apply(gdf_gen.get_planar_area) * 100
        tvlu['dem_luv'] = tvlu['dem_lu'] * tvlu['a_luv'] / tvlu['a_lu']
        tvlugrp = tvlu.groupby(['ID_l', 'lu'])[['a_luv', 'dem_luv']].sum()
        tvlugrp = tvlugrp.reset_index().groupby('ID_l').agg(list)

        tvch = gdf_gen.gdfs_intersection(tv, ch)
        tvch = tvch.rename(columns={'tag_r': 'ch', 'dem': 'dem_ch'})
        tvchgrp = (tvch.groupby('ID_l')[['ch', 'dem_ch']].sum())

        tv = pd.concat([tv, tvlugrp, tvchgrp], axis=1)

        for col in ['lu', 'a_luv', 'dem_luv']:
            isna = tv[col].isna()
            tv.loc[isna, col] = pd.Series([[]] * isna.sum()).values
        tv.fillna(value=0, inplace=True)

        tv['demand'] = tv.apply(lambda r: sum(r['dem_luv']) + r['dem_ch'], axis=1)

        return tv

    def dem_lu(div, lu0):
        dlu = gdf_gen.gdfs_intersection(div, lu)
        dlu = dlu.rename(columns={'tag': 'lu', 'area': 'a_lu', 'dem': 'dem_lu'})
        dlu['a_lud'] = dlu['geometry'].apply(gdf_gen.get_planar_area) * 100
        dlu['dem_lud'] = dlu['dem_lu'] * dlu['a_lud'] / dlu['a_lu']
        dlugrp = dlu.groupby(['ID_l', 'lu'])[['a_lud', 'dem_lud']].sum()
        dlugrp = dlugrp.reset_index().groupby('ID_l').agg(list)
        return dlugrp
   
    def dem_ch(div, ch0):
        if ch0.empty:
            return pd.DataFrame(columns=['ch', 'dem_ch'])
        dch = gdf_gen.gdfs_intersection(div, ch)
        dch = dch.rename(columns={'tag': 'ch', 'dem': 'dem_ch'})
        dchgrp = dch.groupby('ID_l')[['ch', 'dem_ch']].sum()
        return dchgrp

    def add_lu_ch(div, lu0, ch0):
        lu_ch = pd.concat([div, dem_lu(div, lu0), dem_ch(div, ch0)], axis=1)
        lu_ch[['lu', 'a_lud', 'dem_lud']] = lu_ch[['lu', 'a_lud', 'dem_lud']].fillna('').apply(list)
        lu_ch[['ch', 'dem_ch']] = lu_ch[['ch', 'dem_ch']].fillna(0)
        lu_ch['dem'] = lu_ch['dem_lud'].apply(sum) + lu_ch['dem_ch']
        return lu_ch

    # endregion
    lu = cleanup_lu(lu)
    ch = cleanup_ch(ch)

    v = voronoi_around_t(t)
    v = add_lu_ch(v, lu, ch)

    if ut.cf['2']['auto_balance_load']:
        v['cap'] = ((v['dem'] // trc) + 1) * trc
        t['cap'] = v['cap']

    if not d.empty:
        d = transf_within_districts(d, t)
        d = add_lu_ch(d, lu, ch)

    data.update({'ch': ch, 'lu': lu, 't': t, 'v': v, 'd': d})
    return data


def get_graph(data):
    poly = data['poly']
    t, s = (data[typ].copy() for typ in ['t', 's'])
    # Get OSM Street graph + trafos and substations
    G = osm.complement_street_graph(osm.g_from_cities(poly), t, s)
    data['G'] = G
    return data


def complement_transf_sub_data(data):
    def assign_closest_pair(pairs, points):
        def closest_pair_to_transf(point):
            if ut.cf['2']['opt_assign'] == 0:
                lns['ptdist'] = lns['rt_li'].apply(lambda line: shp.distance(line, point))
            elif ut.cf['2']['opt_assign'] == 1:
                lns['ptdist'] = lns['rt_st'].apply(lambda line: shp.distance(line, point))
            elif ut.cf['2']['opt_assign'] == 2:
                ...
            return lns['ptdist'].idxmin()

        pts = points.copy()
        lns = pairs.copy()
        pts['sub_pair'] = pts.apply(lambda row: closest_pair_to_transf(row['geometry']), axis=1)
        return pts

    def add_sp_routes(s_p, G):
        s_p['rt_li'] = s_p.apply(lambda r: shpg.LineString([r['geometry_1'].centroid, r['geometry_2'].centroid]),
                                 axis=1)
        s_p['rt_li_l'] = s_p['rt_li'].apply(gdf_gen.get_planar_length)
        gxy = vrp.xy_from_graph(G)
        s_p['rt_st'] = s_p.apply(lambda r: shp.LineString([
            gxy[node] for node in ox.routing.shortest_path(
                G, r['ID_1'], r['ID_2'], weight='length')
        ]), axis=1)
        s_p['rt_st_l'] = s_p['rt_st'].apply(gdf_gen.get_planar_length)
        return s_p

    G = data['G']
    t, sp = (data[typ].copy() for typ in ['t', 'sp'])
    sp = add_sp_routes(sp, G)
    t = assign_closest_pair(sp, t)
    data.update({'t': t, 'sp': sp})
    return data
