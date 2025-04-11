import pandapower as ppp
import pp
import utils as ut
import easygui as ez
import mapping
import os
import stages


def loadsfactor(net, el):
    ib_d = {
        'msg': 'Enter an integer percent factor',
        'lowerbound': 0,
        'upperbound': 1000,
        'default': 100
    }
    net['load']['p_mw'] *= (ez.integerbox(**ib_d) / 100)
    return net


def midswitches(net, el):  # Flip all mid-line switches off
    s_d = {n: False for sw, n in el['switches']['sw'].items()}
    return flip_switches(net, el, s_d)


def suboffline(net, el):
    s = ut.data_un('data.pkl')['s']
    n = ez.multchoicebox(msg='Which  substation(s)', choices=s['name'])
    osmid = s.loc[s['name'].isin(n)].index.tolist()
    netindex = [v for k, v in el['trafos'].items() if k in osmid]
    net['trafo'].loc[netindex, 'in_service'] = False
    return net


def oneoffline(net, el):
    eltype_d = {'Line': 'line', 'Bus': 'bus'}
    eltype_i = ez.indexbox(
        msg='What type of element should be taken offline?',
        title='Element type',
        choices=list(eltype_d.keys()))
    eltype = eltype_d[list(eltype_d.keys())[eltype_i]]
    elid = ez.integerbox(
        msg='Enter the element ID to take offline',
        title='Element ID',
        lowerbound=1,
        upperbound=len(net[eltype]))
    net[eltype].loc[elid, 'in_service'] = False
    return net


def scenario_2(net, el, name, close_aux_switches, data):  # Take one substation offline
    s = ut.data_un('data.pkl')['s']
    # osmid = s.loc[s['name'] == name].index.tolist()[0]
    osmid = s.loc[s['name'].isin(name)].index.tolist()
    # netindex = el['trafos'][osmid]
    netindex = [v for k, v in el['trafos'].items() if k in osmid]
    net['trafo'].loc[netindex, 'in_service'] = False
    if close_aux_switches:
        lineas = [v for k, v in el['lines']['ss'].items()]  # connect only missing sub or all subs
        suiches = net['switch'][net['switch']['element'].isin(lineas)]
        s_d = {swrow.name: True for _, swrow in suiches.iterrows()}
        flip_switches(net, el, s_d)
    return net


def connectaux(net, el):
    # suiches = net['switch'][net['switch']['element'].isin([v for k, v in el['lines']['ss'].items()])]
    # s_d = {swrow.name: True for _, swrow in suiches.iterrows()}
    return flip_switches(net, el, {swid: True for swid in el['switches']['ss'].values()})


def flip_switches(net, el, s_d):
    s_df = {k: v for k, v in s_d.items() if net['switch'].loc[k, 'closed'] != v}
    s_data = net['switch'].loc[s_df.keys()].copy()
    typs = s_data['name'].apply(lambda nx: pp.find_switch_type(nx, el))
    net['switch'].drop(s_df.keys(), inplace=True)
    s_data['closed'] = s_df.values()
    for i, r in s_data.iterrows():
        ns = ppp.create_switch(net, **r)
        net['line'].loc[net['switch'].loc[ns, 'element'], 'in_service'] = r['closed']
        el['switches'][typs[i]][r['name']] = ns
    return net


def run_scenarios(data):
    if data['last_saved'] < 7:
        runall = ez.ynbox(
            'You need to run all remaining stages before running the pandapower module. Would you like to do it now?')
        if runall:
            stages.run_stages(data, stend=(data['last_saved'] + 1, 7))
            data = ut.data_un('data.pkl')
        else:
            exit(0)
    c = data['poly'].centroid
    s = data['s']
    yn_d = {
        'title': 'Re-create network?',
        'msg': 'A base network already exists. It can be used if the grid is not modified. Replace it?',
        'choices': ['Yes, create new network', 'No, reuse existing network'],
        'default_choice': 'No, reuse existing network',
        'cancel_choice': 'No, reuse existing network'
    }
    if os.path.exists('net0.pkl'):
        rerun = (ez.ynbox(**yn_d))
    else:
        rerun = True
    net0, el0 = pp.populate_net(data) if rerun else (ut.data_un('net0.pkl'))
    ut.data_p((net0, el0), 'net0.pkl')
    scenarios_d = {
        'title': 'Choose changes to base network',
        'msg': 'Select scenario(s) to apply',
        'choices': sc_d.keys(),
    }
    scenarios = ez.multchoicebox(**scenarios_d)
    case = ''
    if scenarios is not None:
        for scenario in scenarios:
            func = sc_d[scenario]
            net = func(net0, el0)
            case += f'{scenario}'
        net1 = pp.run_net(net0)
        ppp.to_json(net1, 'ppnet.json')
        mapping.save_map(mapping.pp_network(net1, el0, data), case)


sc_d = {
    'Loads factor': loadsfactor,
    'Open mid-line switches': midswitches,
    'Substation(s) offline': suboffline,
    'One element offline': oneoffline
}

if __name__ == '__main__':
    run_scenarios(ut.data_un('data.pkl'))
