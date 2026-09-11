"""Export lightweight, attributed presentation geometry from the reference files."""
import csv
import json
import shutil
import pickle
import random
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/novi_sad/reference/generated'
TARGET = ROOT / 'web/public/presentation/geography.json'

def street_geometry():
    """Read this checkout's trusted OSM cache, never a downloaded pickle."""
    import networkx as nx
    cache = ROOT / 'data/cache/data.pkl'
    with cache.open('rb') as stream:
        graph = pickle.load(stream)['G']
    streets = nx.DiGraph()
    allowed = {'residential', 'living_street', 'service', 'unclassified', 'tertiary',
               'secondary', 'primary', 'trunk', 'primary_link', 'secondary_link', 'tertiary_link'}
    for u, v, edge in graph.edges(data=True):
        highway = edge.get('highway', [])
        if isinstance(highway, str): highway = [highway]
        if not allowed.intersection(highway): continue
        a, b = graph.nodes[u], graph.nodes[v]
        if not all(19.70 < p['x'] < 20.00 and 45.19 < p['y'] < 45.36 for p in (a,b)): continue
        coords = list(edge['geometry'].coords) if edge.get('geometry') is not None else [(a['x'],a['y']),(b['x'],b['y'])]
        if abs(coords[-1][0]-a['x']) + abs(coords[-1][1]-a['y']) < abs(coords[0][0]-a['x']) + abs(coords[0][1]-a['y']): coords.reverse()
        coords = [[round(p[0],7),round(p[1],7)] for p in coords]
        length = float(edge.get('length',1))
        if not streets.has_edge(u,v) or streets[u][v]['length'] > length:
            streets.add_edge(u,v,length=length,coords=coords)
    # Use actual directed connectivity so cars do not reverse a one-way street.
    component = max(nx.strongly_connected_components(streets), key=len)
    connected = streets.subgraph(component)
    rng = random.Random(41001)
    starts = [n for n in sorted(component) if 19.79 < graph.nodes[n]['x'] < 19.88 and 45.23 < graph.nodes[n]['y'] < 45.30]
    paths = []
    for start in rng.sample(starts,min(36,len(starts))):
        walk=[start]
        for _ in range(65):
            choices=sorted(connected.successors(walk[-1]))
            forward=[n for n in choices if len(walk)<2 or n != walk[-2]]
            walk.append(rng.choice(forward or choices))
        walk.extend(nx.shortest_path(connected,walk[-1],start,weight='length')[1:])
        path=[]
        for u,v in zip(walk,walk[1:]):
            segment=connected[u][v]['coords']
            path.extend(segment if not path else segment[1:])
        if len(path)>2 and path[0]==path[-1]: paths.append(path)
    unique = {}
    for _,_,edge in streets.edges(data=True):
        line=edge['coords']; key=min(tuple(map(tuple,line)),tuple(map(tuple,reversed(line))))
        unique[key]=line
    return list(unique.values()), paths, hashlib.sha256(cache.read_bytes()).hexdigest()

def main():
    with (SOURCE / 'novi_sad_synthetic_transformers.csv').open(encoding='utf-8-sig') as stream:
        points = [[round(float(r['longitude']), 7), round(float(r['latitude']), 7),
                   round(float(r['peak_demand_mw']), 4)] for r in csv.DictReader(stream)]
    feeders = json.loads((SOURCE / 'novi_sad_inferred_feeders.geojson').read_text())
    routes = []
    for feature in feeders['features']:
        geometry = feature['geometry']
        lines = [geometry['coordinates']] if geometry['type'] == 'LineString' else geometry['coordinates']
        for line in lines:
            routes.append([[round(p[0], 7), round(p[1], 7)] for p in line])
    stations = json.loads((SOURCE / 'novi_sad_seeded_substations.json').read_text())
    roads, car_paths, cache_hash = street_geometry()
    payload = {'attribution': '© OpenStreetMap contributors · ODbL. Adapted from the repository reference model; upstream method: Gebhard, Tundis & Steinke.',
               'status': 'Synthetic planning proxy. Service-point columns are symbolic, not surveyed buildings. Feeder routes and most station coordinates are inferred.',
               'points': points, 'routes': routes, 'roads': roads, 'carPaths': car_paths,
               'roadSource': 'Local cached OSM street graph, motor-road tags, original directed connectivity. Vehicle positions/speeds are illustrative.',
               'roadSnapshotSha256': cache_hash,
               'stations': [{'name': s['name'], 'lon': s['lon'], 'lat': s['lat']} for s in stations['primary_stations']]}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    shutil.copyfile(ROOT / 'artifacts/novi_sad/reference/maps/novi_sad_simulation_map.html', TARGET.parent / 'map.html')
    evidence = TARGET.parent / 'sources'
    evidence.mkdir(exist_ok=True)
    for source in ['artifacts/benchmark-five-page-report/report-final.md', 'artifacts/challenge-study-v2/report-final.md', 'docs/models/novi-sad.md',
                   'docs/presentation-algorithm-research.md','docs/presentation-daily-energy.md', 'docs/models/ev-playground.md', 'docs/gui-workflow.md', 'docs/reproducibility.md', 'docs/strategy-development.md',
                   'docs/agent-contract.md', 'docs/benchmark.md', 'docs/continuous-rl.md', 'docs/node-aggregation.md', 'docs/whole-day-charging.md']:
        source_path = ROOT / source
        (evidence / (source.replace('/', '__') + '.txt')).write_text('Source: ' + source + '\n\n' + source_path.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'Exported {len(points)} service points, {len(routes)} routes, {len(payload["stations"])} stations to {TARGET}')
    print(f'Roads: {len(roads)}; closed vehicle paths: {len(car_paths)}')

if __name__ == '__main__':
    main()

