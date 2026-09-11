from . import utils as ut
import shapely.geometry as shpg
import shapely.ops as shpo
import osmnx as ox
import osmnx.settings
import geopandas as gpd
import overpy
import requests
from .gdf_gen import get_planar_length as pl
from tqdm import tqdm

osmnx.settings.bidirectional_network_types = ["all", "all_public", "bike", "drive", "drive_service", "walk"]
ov_api = overpy.Overpass()


def op_query(query):
    global ov_api
    errors = []
    for endpoint in ('https://overpass-api.de/api/interpreter',
                     'https://overpass.kumi.systems/api/interpreter',
                     'https://overpass.private.coffee/api/interpreter'):
        try:
            response = requests.get(endpoint, params={'data': query},
                                    headers={'User-Agent': 'MVGridModelGenerator/1.0'}, timeout=90)
            response.raise_for_status()
            return ov_api.parse_xml(response.content)
        except (requests.RequestException, ValueError) as error:
            errors.append(f'{endpoint}: {error}')
    raise RuntimeError(f'All Overpass endpoints failed: {" | ".join(errors)}')


def op_query_json(query):
    errors = []
    for endpoint in ('https://overpass-api.de/api/interpreter',
                     'https://overpass.kumi.systems/api/interpreter',
                     'https://overpass.private.coffee/api/interpreter'):
        try:
            response = requests.get(endpoint, params={'data': query},
                                    headers={'User-Agent': 'MVGridModelGenerator/1.0'}, timeout=90)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            errors.append(f'{endpoint}: {error}')
    raise RuntimeError(f'All Overpass endpoints failed: {" | ".join(errors)}')


def overpass_query_dict_to_text(qd: dict, poly) -> str:
    def nwr_d2s(nwr: dict):
        nwr_str = '; '.join(typ_l
                            for typ_l in (
                                f'{typ}(id:{",".join(str(osmid) for osmid in ids)})'
                                for typ, ids in nwr.items()))
        return f'({nwr_str};)' if len(nwr) > 1 else nwr_str

    in_s = nwr_d2s(qd.get('in_nwr', {}))
    ex_s = nwr_d2s(qd.get('ex_nwr', {}))
    q_text = f'{qd.get("nwr", "")}{qd.get("in_tag", "")}{"".join(qd.get("ex_tag", []))}'
    q_text += f'(poly:"{" ".join([f"{lat} {lon}" for lon, lat in poly.exterior.coords])}");' if q_text else q_text
    q_text = f'({q_text}{in_s};);' if in_s else q_text
    q_text = f'({q_text} - {ex_s};);' if ex_s else q_text
    q_text = f'{q_text}{qd["out"]};'
    return q_text


def get_cities_polygon() -> shpg.Polygon:
    """
    Generates a shapely polygon representing the union of the polygons of a given list of cities,
    if they are adjacent to the first city on the list. The parameters cities_list and tolerance
    (to simplify the resulting polygon) are set in the config.json file.
    :return: A polygon representing the union of the polygons of the cities.
    """
    cities_list = ut.cf['1']['cities_list']
    tolerance = ut.cf['2']['simplify_polygon_tolerance']
    main_city = cities_list[0]
    poly = shpg.Polygon()
    while cities_list:
        city = cities_list.pop(0)
        city_polygon = ox.geocode_to_gdf(city)["geometry"].unary_union
        if city_polygon.geom_type == "MultiPolygon":
            largest_polygon = max(city_polygon.geoms, key=lambda p: p.area)
            city_polygon = largest_polygon
        if city == main_city or poly.touches(city_polygon):
            poly = poly.union(city_polygon)
        else:
            cities_list.append(city)
    return poly.simplify(tolerance, preserve_topology=True) if tolerance else poly


@ut.runtime_counter('Retrieving street graph for cities from OSM')
def g_from_cities(poly):
    return ox.graph.graph_from_polygon(poly, **ut.cf['2']['osm_street_graph_options'])


# noinspection PyProtectedMember
def gdf_from_osm(qt, poly):
    def add_elem_to_list(elem, geom, typ, elem_l):
        data_d = {'ID': elem.id,
                  'type': typ,
                  'tag': elem.tags.get(qd.get('tag', ''), ''),
                  'name': elem.tags.get('name', ''),
                  'geometry': geom}
        tfd = {'n': 'node', 'w': 'way', 'r': 'relation'}
        cols = qd.get('in_nwr', {}).get(tfd[typ], {}).get(str(elem.id))
        data_d.update(cols) if cols else None
        # if cols:
            # for k, v in cols.items():
                # if k in data_d:
                #     data_d[k] = v
                # else:
                #     data_d.setdefault('etc', {})[k] = v
        elem_l.append(data_d)

    qd = ut.cf['1']['queries'][qt]
    if qd.get('disabled', False):
        return gpd.GeoDataFrame(columns=['ID', 'type', 'tag', 'name', 'geometry'],
                                geometry='geometry', crs='WGS84').set_index('ID')
    query_text = '[out:json];' + overpass_query_dict_to_text(qd, poly)
    print("Overpass query:", query_text)
    elements = op_query_json(query_text)['elements']
    rows, relation_way_ids = [], set()
    for element in elements:
        if element['type'] == 'relation':
            relation_way_ids.update(member['ref'] for member in element.get('members', []) if member['type'] == 'way')
    for element in tqdm(elements, desc=ut.pad_center(qd['type'], 24), colour='green', unit=' geom'):
        typ = element['type']
        if typ == 'way' and element['id'] in relation_way_ids:
            continue
        if typ == 'node':
            geometry = shpg.Point(float(element['lon']), float(element['lat']))
        elif typ == 'way':
            coords = [(float(point['lon']), float(point['lat'])) for point in element.get('geometry', [])]
            if len(coords) < 2:
                continue
            geometry = shpg.Polygon(coords) if len(coords) >= 3 and coords[0] == coords[-1] else shpg.LineString(coords)
        elif typ == 'relation':
            outer_lines = [shpg.LineString([(float(point['lon']), float(point['lat'])) for point in member['geometry']])
                           for member in element.get('members', [])
                           if member.get('role') == 'outer' and member.get('geometry')]
            polygons = list(shpo.polygonize(outer_lines))
            if not polygons:
                continue
            geometry = shpo.unary_union(polygons)
        else:
            continue
        row = {'ID': element['id'], 'type': typ[0], 'tag': element.get('tags', {}).get(qd.get('tag', ''), ''),
               'name': element.get('tags', {}).get('name', ''), 'geometry': geometry}
        configured = qd.get('in_nwr', {}).get(typ, {}).get(str(element['id']))
        if configured:
            row.update(configured)
        rows.append(row)
    return gpd.GeoDataFrame(rows, crs='WGS84').set_index('ID')


def get_city_polygon(data):
    data[1] = {'poly': get_cities_polygon()}
    return data


@ut.runtime_counter('Adding Transformers and Substations to the Graph')
def complement_street_graph(G, tr, sub):
    def add_n_e(gdf):
        n_e = gdf.apply(lambda r: Ge_i.nearest(r['geometry'])[1][0], axis=1)
        s_l = gdf.shortest_line(Ge.iloc[n_e], align=False)

        G.add_nodes_from(
            [node for lst in gdf.apply(
                lambda r: [(r['ID'], {'x': s_l[r.name].coords[0][0], 'y': s_l[r.name].coords[0][1]}),
                           (r['ID'] * 1000, {'x': s_l[r.name].coords[1][0], 'y': s_l[r.name].coords[1][1]})],
                axis=1).tolist() for node in lst])

        G.add_edges_from(
            [edge for lst in gdf.apply(
                lambda r: [
                    (r['ID'],
                     r['ID'] * 1000,
                     {'length': pl(s_l[r.name])}),
                    (r['ID'] * 1000,
                     r['ID'],
                     {'length': pl(s_l[r.name])}),
                    (Ge.iloc[n_e[r.name]].name[0],
                     r['ID'] * 1000,
                     {'length': pl(shpg.LineString(
                         [s_l[r.name].coords[1],
                          Ge.iloc[n_e[r.name]]['geometry'].coords[0]]))}),
                    (r['ID'] * 1000,
                     Ge.iloc[n_e[r.name]].name[0],
                     {'length': pl(shpg.LineString(
                         [s_l[r.name].coords[1],
                          Ge.iloc[n_e[r.name]]['geometry'].coords[0]]))}),
                    (Ge.iloc[n_e[r.name]].name[1],
                     r['ID'] * 1000,
                     {'length': pl(shpg.LineString(
                         [s_l[r.name].coords[1],
                          Ge.iloc[n_e[r.name]]['geometry'].coords[1]]))}),
                    (r['ID'] * 1000,
                     Ge.iloc[n_e[r.name]].name[1],
                     {'length': pl(shpg.LineString(
                         [s_l[r.name].coords[1],
                          Ge.iloc[n_e[r.name]]['geometry'].coords[1]]))})],
                axis=1).tolist() for edge in lst])
    Gn, Ge = ox.graph_to_gdfs(G)
    Ge_i = Ge.sindex
    add_n_e(tr.copy().reset_index())
    add_n_e(sub.copy().reset_index())
    return G
