import utils as ut
import gdf_alg as gdf
import vrp
import easygui
from functools import wraps


class StageManager:
    def __init__(self):
        self.TEXT = {
            1: 'Get cities region, execute Overpass queries and create GeoDataFrames',
            2: 'Process demand data with land use and EV Chargers',
            3: 'Get street graph and add trafos and substations',
            4: 'Assign transformers to substation pairs',
            5: 'Prepare directed graphs for VRP',
            6: 'Run VRPy to generate line solutions for each substation pair',
            7: 'Post-process VRPy solutions',
        }
        self.FUNCTIONS = {
            1: gdf.create_gdfs,
            2: gdf.extend_gdf_data,
            3: gdf.get_graph,
            4: gdf.complement_transf_sub_data,
            5: vrp.create_digraphs,
            6: vrp.solve_vrpy,
            7: vrp.complement_sols,
        }

    def load_save_stage(self, num):
        def decorator(func):
            @wraps(func)
            def wrapper(data):
                print(f'\n\nStage {num}: {self.TEXT[num]}')
                data = ut.data_un('data.pkl')
                if True:
                    data = func(data)
                    data['last_saved'] = num
                    ut.data_p(data, 'data.pkl')
                return data
            return wrapper
        return decorator


def run_stages(data, stend=(1, 7)):
    sm = StageManager()
    if stend is None:
        st = 1
        lastsaved = data['last_saved']
        if lastsaved > 1:
            st = easygui.choicebox(
                title='Starting Stage',
                msg=f'The last saved stage is stage {lastsaved}. Where would you like to start? (Canceling starts at 1)',
                choices=[f'{num}.-{sm.TEXT[num]}' for num in range(
                    1, min(lastsaved + 2, len(sm.TEXT)))],
                preselect=lastsaved + 1)
            st = 1 if st is None else int(st[:1])
        if st < len(sm.TEXT):
            end = easygui.choicebox(
                title='Last  Stage',
                msg=f'The algorithm will start on stage {st}. ' 
                    f' Until which stage would you like to run? (Canceling runs to the end)',
                choices=[f'{num}.-{sm.TEXT[num]}' for num in range(st, len(sm.TEXT)+1)],
                preselect=0)
            end = len(sm.TEXT) if end is None else int(end[:1])
        else:
            end = len(sm.TEXT)
    else:
        st, end = stend
    # data = {}
    for num in range(st, end+1):
        func = sm.FUNCTIONS[num]

        @sm.load_save_stage(num)
        def stage(d):
            return func(d)

        data = stage(data)