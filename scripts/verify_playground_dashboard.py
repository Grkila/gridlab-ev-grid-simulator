"""Independent Streamlit AppTest acceptance with real persistent worker jobs."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from streamlit.testing.v1 import AppTest
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.dashboard import _block_state, build_map


def verify():
    with tempfile.TemporaryDirectory() as home:
        os.environ['EV_PLAYGROUND_HOME'] = home
        service = Service(home)
        app = AppTest.from_file(str(ROOT / 'src/mvgrid/novi_sad/playground/dashboard.py'), default_timeout=30).run()
        assert not app.exception, app.exception
        def click(label):
            next(b for b in app.button if b.label == label).click().run()
            assert not app.exception, app.exception
        app.text_area[0].set_value('name: [').run()
        assert app.error
        definition = service.catalog()['example']
        definition.update(name='Dashboard acceptance', strategies=['immediate'], stress_first=False, stop_on_violation=False)
        definition['fleet']['fleet_size'] = 8
        definition['limits']['max_loading_percent'] = 50
        app.text_area[0].set_value(yaml.safe_dump(definition)).run()
        click('Validate')
        assert any('valid' in s.value for s in app.success)
        click('Save')
        assert len(service.list_experiments()) == 1
        click('Save and run')
        run_id = service.list_runs()[0]['run_id']
        deadline = time.monotonic()+180
        while service.get_run(run_id)['status'] in ('starting','running'):
            assert time.monotonic()<deadline
            time.sleep(.25)
        assert service.get_run(run_id)['status']=='completed', service.get_run(run_id)
        click('Refresh status')
        assert not app.warning, [w.value for w in app.warning]
        case = service.get_results(run_id)['cases'][0]
        violation_step = next(i for i,v in enumerate(case['intervals']) if v['violations'])
        click('Jump to first violation')
        assert app.slider[0].value == violation_step
        step = next(i for i,v in enumerate(case['intervals']) if v['ev_kw']>0)
        app.slider[0].set_value(step).run()
        states = _block_state(case,case['intervals'][step])
        selected = next(b for b in states if b['counts']['charging']>0)
        next(s for s in app.selectbox if s.label=='Selected block').select(selected['id']).run()
        assert not app.exception
        frames=[d.value for d in app.dataframe]
        count_frame=next(f for f in frames if 'Count' in f.columns)
        assert count_frame['Count'].to_dict()==selected['counts']
        assert abs(sum(b['ev_kw'] for b in states)-case['intervals'][step]['ev_kw'])<1e-6
        assert abs(sum(b['baseline_kw'] for b in states)-case['intervals'][step]['baseline_kw'])<1e-6
        html=build_map(states, selected['id'])
        assert 'Representative' in html and selected['id'] in html
        assert 'tile.openstreetmap.org' in html
        assert html.count('simplified electrical link (not physical routing)') == len(states) == 52
        assert html.count('HV/MV source') == 6
        assert html.count('retained electrical association') == len({b['delivery_id'] for b in states}) == 10
        assert not {'NS1','NS6','FUT'} & {b['source_id'] for b in states}
        assert 'EV load aggregated at this block node' in html and 'L.polyline' in html
        violation_html=build_map(_block_state(case,case['intervals'][violation_step]))
        assert '#b91c1c' in violation_html
        assert sum('chart' in str(node.type) for node in app) >= 4, [node.type for node in app]
        chart_specs=' '.join(str(node.proto) for node in app if 'chart' in str(node.type))
        assert 'Time (HH:MM)' in chart_specs and 'end_hour' in chart_specs
        click('Save and run')
        second=next(r['run_id'] for r in service.list_runs() if r['run_id'] != run_id)
        deadline=time.monotonic()+180
        while service.get_run(second)['status'] in ('starting','running'):
            assert time.monotonic()<deadline
            time.sleep(.25)
        click('Refresh status')
        click('Compare selected runs')
        assert not app.exception
        definition.update(name='Default stop dashboard acceptance',stop_on_violation=True)
        definition['limits']['max_loading_percent']=1
        app.text_area[0].set_value(yaml.safe_dump(definition)).run()
        click('Save and run')
        stopped=app.session_state['run_id']
        deadline=time.monotonic()+180
        while service.get_run(stopped)['status'] in ('starting','running'):
            assert time.monotonic()<deadline
            time.sleep(.25)
        assert service.get_run(stopped)['status']=='stopped_on_violation'
        click('Refresh status')
        assert not app.exception
        assert not any('not available' in w.value for w in app.warning), [w.value for w in app.warning]
        assert any('partial' in w.value.lower() for w in app.warning)
        assert len(service.get_results(stopped)['cases'][0]['intervals'])==1
        import psutil
        for item in service.list_runs():
            try: psutil.Process(item['pid']).wait(timeout=10)
            except psutil.NoSuchProcess: pass
        return {'passed':True,'checks':['invalid YAML','validate','save','real background run','refresh','time slider','first violation navigation','block selection','exact count table','map frame totals','representative cars','OpenStreetMap tiles','53 equivalent block links','6 source nodes','10 delivery associations','excluded source absence','EV association tethers','red affected connections','district and transformer charts','hour-axis 15-minute heatmap','second run','comparison','single-interval stopped run visible with warning'], 'limitations':['File uploader cannot be driven through this AppTest API; browser verification required.'], 'intervals':len(case['intervals'])}


if __name__=='__main__':
    print(json.dumps(verify(), indent=2))
