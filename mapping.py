import folium
import shapely as shp
import geopandas as gpd
import pandas as pd
import branca
from branca.element import Template, MacroElement
from branca.colormap import LinearColormap
import utils as ut
import matplotlib.pyplot as plt
import io
import ppscenarios
import base64
from folium.plugins.treelayercontrol import TreeLayerControl
import gdf_gen
import numpy as np
import easygui as ez
import stages
import os

tfd = {'n': 'Node', 'w': 'Way', 'r': 'Relation', 's': 'Special', 'm': 'Manual'}
color_t10 = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
             "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"]


def join_tables(tables_d):
    return '<div style="height: 10px; border-bottom: 1px solid #000;"></div> '.join(tables_d.values())


def units_formatter(c):
    return '{:.' + str({'MW': 3, 'ha': 2, 'km': 2}.get(c[c.rfind('(') + 1:-1] if '(' in c else None, 0)) + 'f}'


def align_decimals(val):
    if isinstance(val, (int, float)):
        formatted_val = f'{val:,.2f}'
        try:
            comma_index = formatted_val.index('.')
            return f'<div style="text-align: right; margin-left: {comma_index}ch;">{formatted_val}</div>'
        except ValueError:
            return f'<div style="text-align: right;">{formatted_val}</div>'
    return val


def mapgdftest(gdflist):
    m = folium.Map(location=[49.8667, 8.6500], zoom_start=13)
    for i, gdf in enumerate(gdflist):
        folium.GeoJson(gdf, color=color_t10[i], marker=folium.CircleMarker(radius=2)).add_to(m)
    m.save('mapgdftest.html')


def stylecommon(df):
    cts = [
        {
            "selector": "th",
            "props": [
                ("background-color", "#cccccc"),
                ("text-align", "center"),
                ("font-weight", "bold"),
                ("font-size", "10pt"),
                ("padding", "7px"),
                ("border-bottom", "1px solid #ddd"),
            ],
        },
        {
            "selector": "td",
            "props": [
                ("padding", "5px"),
                ("text-align", "center"),
                ("font-size", "11pt"),
            ],
        },
        {
            "selector": "tr:nth-child(even)",
            "props": [("background-color", "#cccccc")],
        },
        {
            "selector": "table",
            "props": [("border-collapse", "collapse")],
        },
    ]
    dfs = df.style
    dfs.format({c: units_formatter(c) for c in df.select_dtypes(include='number').columns})
    dfs.set_table_styles(cts)
    return dfs


def stylemap1(df, typ, maxdiff):
    dfs = stylecommon(df)
    dfs.hide(axis=0)
    if typ == 'dif':
        dfs.format('{:.0f}', subset=['Eqv. Std. Trafos']).background_gradient(
            gmap=df['Capacity Shortfall (MW)'], cmap='PuRd', vmin=0, vmax=maxdiff, axis=0)
    elif typ == 'lu':
        dfs.format(lambda x: x.capitalize(), subset=['Land Use Type'])
    return dfs


def stylemap2(df, typ):
    dfs = stylecommon(df)
    if typ in ['pl', 'tot']:
        dfs.hide(['route', 'r_og', 'geometry'], axis='columns')
        # dfs.set_table_styles([{'selector': 'td', 'props': [('font-size', '10pt;')]}])
    if typ in ['sl']:
        dfs.hide(['type', 'tag', 'pairs', 'geometry'], axis='columns')
        dfs.hide(axis=0)
        dfs.relabel_index(['Name', 'Lines'], axis=1)
    return dfs


def stylemappandasub(df):
    dfs = stylecommon(df)
    dfs.hide(axis=0)
    dfs.hide('ID', axis=1)
    dfs.relabel_index(['Substation', 'Loading %'], axis=1)
    dfs.format('{:.2f}', subset=['loading_percent'])
    dfs.background_gradient(
        gmap=df['loading_percent'], cmap='RdYlGn_r', vmin=0, vmax=90, axis=0)
    return dfs


def hex_to_rgb(hex_colors):
    return np.array([tuple(int(str(c).lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) for c in hex_colors])


def get_bg_colors(values, cmap):
    return [cmap(v) if not np.isnan(v) else '#000000' for v in values]


def get_text_colors(hex_colors):
    return [
        'black' if (0.2126*r + 0.7152*g + 0.0722*b)/255 > 0.5 else 'white'
        for r, g, b in [
            tuple(int(c.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) for c in hex_colors
        ]
    ]


def get_simpletooltips(gdf):
    opacity = 0.75
    rgb_colors = hex_to_rgb(gdf['bgcolor'].values)
    r, g, b = rgb_colors[:, 0], rgb_colors[:, 1], rgb_colors[:, 2]
    return [
        f"""
        <div style="font-size: 20px; text-align: center; background-color: rgba({r[i]}, {g[i]}, {b[i]}, {opacity}); color: {gdf['txtcolor'].iloc[i]};">
          Element ID: {i}<br>
          {gdf.columns[0]}: <b>{f'{gdf.iloc[i, 0]:.2f}' if not pd.isna(gdf.iloc[i, 0]) else 'Disconnected'}</b>
        </div>
        """
        for i in range(len(gdf))
    ]


def plt_hist(data_col, ylabel, bins=10, alpha=0.75, colormap=None):
    n, bins, patches = plt.hist(data_col, bins=bins, alpha=alpha)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    for i, p in enumerate(patches):
        p.set_facecolor(colormap(bin_centers[i]))
    plt.ylabel(ylabel)
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=60)
    buffer.seek(0)
    plot64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.clf()
    return '<img src="data:image/png;base64,{}">'.format(plot64)


def draggable_box(boxid, html, pagetitle, tabletitle='', pos='right: 20px; bottom: 20px'):
    new_element = MacroElement()
    new_element._template = Template(
        """
        {% macro html(this, kwargs) %}
    
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>""" + pagetitle + """</title>
          <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">
    
          <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
          <script src="https://code.jquery.com/ui/1.12.1/jquery-ui.js"></script>
    
          <script>
          $( function() {
            $( "#""" + boxid + """" ).draggable({
                            start: function (event, ui) {
                                $(this).css({
                                    right: "auto",
                                    top: "auto",
                                    bottom: "auto"
                                });
                            }
                        });
        });
    
          </script>
        </head>
        <body>
    
    
        <div id='""" + boxid + """' class='maplegend'
            style='position: absolute; z-index:9999; border:2px solid grey; background-color:rgba(255, 255, 255, 0.8);
             border-radius:6px; padding: 10px; font-size:14px; """ + pos + """;'>
    
        <div class='legend-title' style='text-align: center; font-weight: bold;'>
        """ + tabletitle + """
        </div>
        <div class='legend-scale'>
          <ul class='legend-labels'>
          """ + html + """
          </ul>
        </div>
        </div>
    
        </body>
        </html>
    
        <style type='text/css'>
          .maplegend .legend-title {
            text-align: left;
            margin-bottom: 5px;
            font-weight: bold;
            font-size: 90%;
            }
          .maplegend .legend-scale ul {
            margin: 0;
            margin-bottom: 5px;
            padding: 0;
            float: left;
            list-style: none;
            }
          .maplegend .legend-scale ul li {
            font-size: 80%;
            list-style: none;
            margin-left: 0;
            line-height: 18px;
            margin-bottom: 2px;
            }
          .maplegend ul.legend-labels li span {
            display: block;
            float: left;
            height: 16px;
            width: 30px;
            margin-right: 5px;
            margin-left: 0;
            border: 1px solid #999;
            }
          .maplegend .legend-source {
            font-size: 80%;
            color: #777;
            clear: both;
            }
          .maplegend a {
            color: #777;
            }
        </style>
        {% endmacro %}
        """
    )
    return new_element


def route_from_gdfs(data):
    # region Constants
    s, sp, t, poly, solgdfs = (data[typ] for typ in ['s', 'sp', 't', 'poly', 'sol_gdfs'])
    mo, stc = (ut.cf[l1][l2] for l1, l2 in zip(['4', '3'], ['2', 'std_transfo_capacity']))
    c = poly.centroid
    m = folium.Map(location=[c.y, c.x], zoom_start=13)
    # endregion

    # region df  preparation
    sols = gpd.GeoDataFrame(pd.concat(
        [gdfgrp.set_index(pd.MultiIndex.from_product([[gdfgn], gdfgrp.index]))
         for gdfgn, gdfgrp in solgdfs.items()], axis=0))

    subct = sp[['ID_1', 'ID_2']].copy()
    subct['ct'] = subct.index.map(dict(sols.groupby(level=0).size()))
    subctst = pd.concat([subct[['ID_1', 'ct']], subct[['ID_2', 'ct']].rename(columns={'ID_2': 'ID_1'})])
    s['Lines'] = subctst.groupby('ID_1')['ct'].sum()
    sols.rename(columns={'length': 'Length (km)', 'load': 'Load (MW)', 'tr_ct': 'Transf'}, inplace=True)
    solstot = pd.DataFrame({
        ('Stat', op): {'route': None, 'r_og': None, 'geometry': None,
                       **sols[['Length (km)', 'Load (MW)', 'Transf']].agg(op)}
        for op in ('sum', 'min', 'mean', 'max')}).T
    sols.index.names = ['Pair', 'Line']
    # endregion

    # region Styling and tables
    dfs = {'pl': sols, 'tot': solstot, 'sl': s}
    stylers = {k: stylemap2(v, k) for k, v in dfs.items()}
    tables_d = {
        'sols': {
            'pos': 'left:20px; bottom:20px',
            'boxid': 'table_sol',
            'pagetitle': 'Distribution Network Map',
            'tabletitle': 'Route statistics',
            'html': join_tables({k: stylers[k].to_html() for k in ['pl', 'tot']})
        },
        'lines': {
            'pos': 'right:20px; bottom:20px',
            'boxid': 'table_sub',
            'pagetitle': 'Distribution Network Map',
            'tabletitle': 'Lines per Substation',
            'html': stylers['sl'].to_html()
        }
    }
    tables_f = {k: m.get_root().add_child(draggable_box(**v)) for k, v in tables_d.items()}

    subs_d = {
        'Polygons': {
            'data': s.reset_index(drop=False),
            'name': 'Substations',
            'style_function': lambda x: mo['sub_style'],
            'tooltip': folium.GeoJsonTooltip(fields=['name', 'ID'], aliases=['Name:', 'OSM ID:'])
        },
        'Circle Markers': {
            'data': s['geometry'].apply(lambda x: x.centroid),
            'marker': folium.CircleMarker(**mo['circle_markers'])
        }
    }
    subs_f = {k: folium.GeoJson(**v).add_to(m) for k, v in subs_d.items()}
    # endregion

    # region Features and treelayercontrol
    grps_l = []
    for gn, grp in solgdfs.items():
        rtes_l = []
        for rn, rte in grp.iterrows():
            r_og = t.loc[rte['r_og'][1:-1]]
            rte_d = {
                'Transformers': {
                    'data': r_og.reset_index(drop=False),
                    'name': f'Line',
                    'marker': folium.Circle(**mo['transf_marker']),
                    'style_function': lambda x: mo['transf_style'],
                    'tooltip': folium.GeoJsonTooltip(fields=['name'], aliases=['Name:'])
                },
                'Circle Markers': {
                    'data': r_og['geometry'].apply(lambda x: x.centroid),
                    'marker': folium.CircleMarker(**mo['circle_markers'])
                },
                'Line': {
                    'data': rte['geometry'],
                    'name': f'Line',
                    'tooltip': folium.Tooltip(
                        f'<b>Line {gn}-{rn}<br>Length: {"{:.2f}".format(rte["length"])} km<br>Load: {rte["load"]} kW</b>'),
                    'style_function': lambda x: mo['route_style']
                }
            }
            rtes_l.append({
                'label': f'<font size="+1">Line {rn}</font>',
                'select_all_checkbox': True,
                'collapsed': True,
                'children': [{'label': k, 'layer': folium.GeoJson(**v).add_to(m)} for k, v in rte_d.items()]
            })

        grps_l.append({
            'label': f'<font size="+1">{gn} : {sp.loc[gn, "name_1"]}-{sp.loc[gn, "name_2"]}</font>',
            'select_all_checkbox': True,
            'collapsed': True,
            'children': rtes_l})

    tree = {'children': [
        {
            'label': '<font size="+1">Substation Pairs</font>',
            'select_all_checkbox': True,
            'children': grps_l
        },
        {
            'label': '<div class="leaflet-control-layers-separator"></div>'
        },
        {
            'label': 'Substations',
            'children': [{'label': k, 'layer': v} for k, v in subs_f.items()]
        }
    ]}
    tlc = TreeLayerControl(overlay_tree=tree).add_to(m)
    # endregion
    return m


def pp_network(net, el, data):
    # region Constants
    c = data['poly'].centroid
    mo = ut.cf['4']['3']
    crs = ut.cf['3']['crs']
    s = data['s']
    sp = data['sp']
    ll, tl, bv = (k for k in mo.keys())
    m = folium.Map(location=(c.y, c.x), zoom_start=13)
    # endregion

    cmaps = {k: LinearColormap(**v['cmap']) for k, v in mo.items()}

    gdf_data = {
        ll: {
            'data': net['res_line']['loading_percent'],
            'geometry': net['line_geodata']['coords'].apply(shp.LineString),
        },
        tl: {
            'data': net['res_trafo']['loading_percent'],
            'geometry': net['trafo'][['name']].merge(s, left_on='name', right_index=True)['geometry']
        },
        bv: {
            'data': net['res_bus']['vm_pu'],
            'geometry': net['bus_geodata'].T.apply(lambda row: shp.Point(row['x'], row['y']))
        }
    }

    gdfs = {
        k: gpd.GeoDataFrame(v, crs=crs)
        .rename(columns={'data': k})
        .assign(
            bgcolor=lambda df: get_bg_colors(df[k].values, cmaps[k]),
            txtcolor=lambda df: get_text_colors(df['bgcolor']),
            tooltip=lambda df: get_simpletooltips(df)
        )
        for k, v in gdf_data.items()
    }
    sub_table = s.copy().reset_index()[['ID', 'name']]
    sub_table['loading_percent'] = net['res_trafo']['loading_percent']
    sts = stylemappandasub(sub_table)

    lgr = {}
    for gn, gr in el['lines'].items():
        if isinstance(gn, int):
            lgr[gn] = {}
            for rn, rt in gr.items():
                lgr[gn][rn] = gdfs[ll].loc[gdfs[ll].index.isin(rt.values())]
        elif gn == 'ss':
            ss = gdfs[ll].loc[gdfs[ll].index.isin(gr.values())]

    hist_d = {
        key: {
            'data_col': gdfs[key][key],
            'ylabel': {bv: 'Buses', ll: 'Lines'}[key],
            'bins': 25,
            'colormap': cmaps[key]
        }
        for key in [ll, bv]
    }
    hist_html = {k: plt_hist(**v) for k, v in hist_d.items()}
    hist_html[tl] = sts.to_html()
    hist_box = {
        ll: {
            'pos': 'right: 20px; bottom: 400px',
            'boxid': 'llhist',
            'tabletitle': f'{ll} distribution',
            'pagetitle': 'PandaPower Results',
            'html': hist_html[ll]
        },
        bv: {
            'pos': 'right: 20px; bottom: 20px',
            'boxid': 'bhist',
            'tabletitle': f'{bv} Distribution',
            'pagetitle': 'PandaPower Results',
            'html': hist_html[bv]
        },
        tl: {
            'pos': 'right: 20px; bottom: 800px',
            'boxid': 'tlhist',
            'pagetitle': 'PandaPower Results',
            'html': hist_html[tl]
        }
    }
    hist_f = {k: m.get_root().add_child(draggable_box(**v)) for k, v in hist_box.items()}

    for _, r in gdfs[tl].iterrows():
        poly_d = {
            'locations': [[y, x] for x, y in list(r['geometry'].exterior.coords)],
            'tooltip': r['tooltip'],
            'fillColor': r['bgcolor'],
            **mo[tl]['style']
        }
        folium.Polygon(**poly_d).add_to(m)
        point = r['geometry'].centroid
        cm_d = {
            'location': (point.y, point.x),
            'fillColor': r['bgcolor'],
            **mo[tl]['circlemarker']
        }
        folium.CircleMarker(**cm_d).add_to(m)

    for _, r in gdfs[bv].iterrows():
        point = r['geometry']
        c_d = {
            'location': (point.y, point.x),
            'fillColor': r['bgcolor'],
            'tooltip': r['tooltip'],
            **mo[bv]['circlemarker']
        }
        folium.CircleMarker(**c_d).add_to(m)
    # region Features and treelayercontrol
    grps_l = []
    grps_d = {}
    lines_f = {}
    for gn, grp in lgr.items():
        rtes_l = []
        grps_d[gn] = {}
        lines_f[gn] = {}
        for rn, rte in grp.items():
            grps_d[gn][rn] = {}
            lines_f[gn][rn] = folium.FeatureGroup(name=f'Line {gn}-{rn}').add_to(m)
            for segn, seg in rte.iterrows():
                grps_d[gn][rn][segn] = {
                    'locations': [[y, x] for x, y in list(seg['geometry'].coords)],
                    'tooltip': seg['tooltip'],
                    'color': seg['bgcolor'],
                    **mo[ll]['style']
                }
                folium.PolyLine(**grps_d[gn][rn][segn]).add_to(lines_f[gn][rn])
            rtes_l.append({
                'label': f'<font size="+1">Line {rn}</font>',
                'collapsed': True,
                'layer': lines_f[gn][rn],
                'name': f'Line {gn}-{rn}'
            })
        grps_l.append({
            'label': f'<font size="+1">{gn} : {sp.loc[gn, "name_1"]}-{sp.loc[gn, "name_2"]}</font>',
            'select_all_checkbox': True,
            'collapsed': True,
            'children': rtes_l})
    # lines_f['ss'] = folium.FeatureGroup(name=f'Auxiliary Lines').add_to(m)
    rtes_l = []
    ss_d = {}
    # for rn, rte in ss.iterrows():
    #     ss_d[rn] = {
    #         'locations': [[y, x] for x, y in list(rte['geometry'].coords)],
    #         'tooltip': rte['tooltip'],
    #         'color': rte['bgcolor'],
    #         **mo[ll]['style']
    #     }
    #     folium.PolyLine(**ss_d[rn]).add_to(lines_f['ss'])
    # grps_l.append({
    #     'label': f'<p style= "font-size: 16px">Auxiliary Lines</font>',
    #     'collapsed': True,
    #     'layer': lines_f['ss'],
    #     'name': f'Auxiliary Lines'
    # })

    tree = {'children': [
        {
            'label': '<font size="+1">Substation Pairs</font>',
            'select_all_checkbox': True,
            'children': grps_l
        },
    ]}
    tlc = TreeLayerControl(overlay_tree=tree).add_to(m)
    # endregion
    return m


def voronoi_transformers(data):
    # region Input and constants
    v, d, lu, t, poly, ch = (data[typ] for typ in ['v', 'd', 'lu', 't', 'poly', 'ch'])
    t = t.reset_index()
    mo, stc = (ut.cf[l1][l2] for l1, l2 in zip(['4', '3'], ['1', 'std_transfo_capacity']))
    c = poly.centroid
    m = folium.Map(location=(c.y, c.x), zoom_start=13, tiles=None)
    mtiles = folium.TileLayer('OpenStreetMap', control=False).add_to(m)

    # endregion

    # region Nested Functions
    def vorostyle(r, linmap):
        s_dic = {'fillColor': linmap(r['diff'])}
        s_dic.update(mo['choro_style'])
        return s_dic

    def tooltip(r, maxd):
        def table(rx, typ):
            if typ == 'lu':
                if not rx['lu']:
                    return None
                else:
                    return pd.DataFrame({
                        'Land Use Type': rx['lu'],
                        'Area (ha)': rx['a_lud'],
                        'Peak Demand (MW)': rx['dem_lud']
                    })
            elif typ == 'ch':
                if rx['ch'] == 0:
                    return None
                else:
                    return pd.DataFrame({
                        'Charger Ports': rx['ch'],
                        'Peak Demand (MW)': rx['dem_ch']
                    }, index=[0])
            elif typ == 'tr':
                nametext = 'Trafo OSM Id' if isinstance(rx['name'], int) else 'District Name'
                return pd.DataFrame({
                    nametext: rx['name'],
                    'Area (ha)': rx['area_cel'],
                    'Capacity (MW)': rx['cap']
                }, index=[0])
            elif typ == 'dif':
                return pd.DataFrame({
                    'Capacity Shortfall (MW)': rx['diff'],
                    'Eqv. Std. Trafos': ((rx['diff'] // ut.cf["3"]["std_transfo_capacity"]) + 1)
                }, index=[0])

        tables = {typ: table(r, typ) for typ in ['lu', 'ch', 'tr', 'dif'] if not table(r, typ) is None}
        tables_s = {typ: stylemap1(df, typ, maxd).to_html() for typ, df in tables.items()}
        return join_tables(tables_s)

    def process_division(cel, name):
        cel['area_cel'] = cel['geometry'].apply(gdf_gen.get_planar_area) * 100
        cel['diff'] = cel['dem'] - cel['cap']
        maxdiff = cel['diff'].abs().max()
        lmap = branca.colormap.linear.PuRd_06.scale(0, maxdiff)
        lmap.caption = f'Capacity Shortfall per {name} Cell (MW)'
        lmap.add_to(m)
        cel['style'] = cel.apply(lambda r: vorostyle(r, lmap), axis=1)
        cel['tooltip'] = cel.apply(lambda r: tooltip(r, maxdiff), axis=1)
    # endregion

    process_division(v, 'Voronoi')
    process_division(d, 'District')
    lu_cd = {lut: color_t10[i + 3] for i, lut in enumerate(lu['tag'].unique())}
    lu['style'] = lu.apply(lambda x: {'fillColor': lu_cd[x['tag']], **mo['land_use']}, axis=1)

    # region Add Layers
    f_args_d = {
        'lu': {
            'data': lu,
            'name': 'Land Use Areas',
        },
        'chcm': {
            'data': ch['geometry'].apply(lambda x: x.centroid),
            'name': 'EV Charger Circle Markers',
            'marker': folium.CircleMarker(**mo['circle_markers_ch'])
        },
        'ch': {
            'data': ch,
            'name': 'EV Chargers',
            'style_function': lambda x: mo['charger_style'],
            'marker': folium.Circle(**mo['charger_marker'])
        },
        'trcm': {
            'data': t['geometry'].apply(lambda x: x.centroid),
            'name': 'Transformer Circle Markers',
            'marker': folium.CircleMarker(**mo['circle_markers_tr'])
        },
        'tr': {
            'data': t,
            'name': 'Transformers',
            'style_function': lambda x: mo['transf_style'],
            'marker': folium.Circle(**mo['transf_marker']),
            'tooltip': folium.GeoJsonTooltip(
                fields=['ID'],
                aliases=['Tr. ID:'],
                style=(
                    'background-color: white; ' +
                    'color: #333333; ' +
                    'font-family: tahoma; ' +
                    'font-size: 16px; ' +
                    'padding: 10px; '
                )
            )
        },
        'v': {
            'data': v,
            'name': 'Voronoi Cells',
            'tooltip': folium.GeoJsonTooltip(
                fields=['tooltip'],
                labels=False
            )
        },
        'd': {
            'data': d,
            'name': 'District Cells',
            'tooltip': folium.GeoJsonTooltip(
                fields=['tooltip'],
                labels=False
            )
        }

    }
    feat_d = {feat: folium.GeoJson(**args).add_to(m) for feat, args in f_args_d.items()}
    db_args_d = {
        'luleg': {
            'boxid': 'table_leg',
            'pagetitle': 'Balancing Load vs Capacity',
            'tabletitle': 'Land Use Types',
            'pos': 'right: 50px; bottom: 50px',
            'html':
                """
                    <div class='my-legend'>
                        <div class='legend-scale'>
                            <ul class='legend-labels'>
                """ +
                '\n'.join(
                    [f"<li><span style='background:{color};'></span>{str.capitalize(lut)}</li>"
                     for lut, color in lu_cd.items()])
                + """
                            </ul>
                    </div>
            </div>
            """
        }
    }
    box_d = {box: m.get_root().add_child(draggable_box(**db)) for box, db in db_args_d.items()}
    folium.ClickForLatLng().add_to(m)
    lc = folium.LayerControl(collapsed=False).add_to(m)
    # endregion
    return m


def save_map(m, typ):
    name = ez.filesavebox(
        msg='Save Map',
        title='Save Map to File',
        default=f'/maps/{typ}.html',
        filetypes=['*.html'])
    if name is None:
        pass
    else:
        # name += '.html' if not name.endswith('.html') else ''
        m.save(name)
        os.startfile(name)


def create_maps(data):
    maps = ez.multchoicebox(
        msg='Select Maps to Create',
        title='Create Maps',
        choices=['1 Land Use Zones', '2 Grid Routing Map', '3 PandaPower Network']
    )
    if maps is not None:
        if '1 Land Use Zones' in maps:
            if data['last_saved'] < 2:
                runall = ez.ynbox('You need to run up to stage 2 before generating the Land Use Map. Would you like to do it now?')
                if runall:
                    stages.run_stages(data, stend=(data['last_saved'] + 1, 2))
                    data = ut.data_un('data.pkl')
                else:
                    exit(0)
            save_map(voronoi_transformers(data), '1 Land Use Zones')
        if '2 Grid Routing Map' in maps:
            if data['last_saved'] < 7:
                runall = ez.ynbox('You need to run all remaining stages before generating the Grid Map. Would you like to do it now?')
                if runall:
                    stages.run_stages(data, stend=(data['last_saved'] + 1, 7))
                    data = ut.data_un('data.pkl')
                else:
                    exit(0)
            save_map(route_from_gdfs(data), '2 Grid Routing Map')
        if '3 PandaPower Network' in maps:
            ppscenarios.run_scenarios(data)


if __name__ == '__main__':
    create_maps()
