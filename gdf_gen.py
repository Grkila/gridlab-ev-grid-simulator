import geopandas as gpd
import pyproj
import utils as ut


def gdfs_intersection(a, b):
    # GeoPandas 0.14 names the right-hand spatial-join index ``index_right``;
    # normalize it so the downstream aggregation code remains version-agnostic.
    a_int_b = a.reset_index(names='ID_l').sjoin(b, lsuffix='l', rsuffix='r').rename(
        columns={'index_right': 'ID_r', 'index_r': 'ID_r'})
    a_int_b['geometry'] = a_int_b.apply(lambda r: r['geometry'].intersection(b.loc[r['ID_r'], 'geometry']), axis=1)
    return a_int_b


def get_planar_area(geom):
    geod = pyproj.Geod(ellps=ut.cf['3']['crs'])
    area, _ = geod.geometry_area_perimeter(geom)
    return abs(area) / 1_000_000


def get_planar_length(geom):
    geod = pyproj.Geod(ellps=ut.cf['3']['crs'])
    return abs(geod.geometry_length(geom)) / 1000


def gdf_deduplicate(gdf: gpd.GeoDataFrame):
    i = 0
    si = gdf.sindex
    while i < len(gdf):
        a = gdf.iloc[i]
        dropped = False
        for j in si.intersection(a.geometry.bounds):
            b = gdf.iloc[j]
            if b.name == a.name:
                continue
            if a.geometry.within(b.geometry):
                gdf.drop(a.name, axis=0, inplace=True)
                dropped = True
                break
            if b.geometry.within(a.geometry):
                gdf.drop(b.name, axis=0, inplace=True)
                dropped = True
                break
        si = gdf.sindex
        if not dropped:
            i += 1


