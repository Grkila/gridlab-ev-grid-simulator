import utils as ut
import osm

data = ut.data_un('data.pkl')

b = osm.gdf_from_osm('b', data[2]['poly'])

breakpoint()
