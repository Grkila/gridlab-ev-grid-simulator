import unittest
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.simulation import Simulator
from mvgrid.novi_sad.playground.node_aggregation import aggregate_sessions


class NodeAggregationTests(unittest.TestCase):
    def test_node_power_rises_and_falls_with_individual_electrical_parity(self):
        _,blocks=build_network()
        sessions=[dict(id=str(i),block_id=blocks[0]['id'],arrival_step=0,departure_step=4,
                       energy_kwh=14.,charger_kw=7.4,efficiency=.9) for i in range(20)]
        individual,aggregate=Simulator(),Simulator()
        individual.reset(dict(strategy='immediate',stop_on_violation=False),[100000.]*4,sessions)
        aggregate.reset(dict(strategy='immediate',stop_on_violation=False,aggregate_ev_nodes=True),[100000.]*4,sessions)
        self.assertEqual(len(aggregate.sessions),1)
        self.assertEqual(aggregate.vehicle_count,20)
        cohort=aggregate.sessions[0]
        for kw in (20.,80.,10.,0.):
            _,a,_=individual.step({s['id']:kw/20 for s in individual.sessions})
            _,b,_=aggregate.step_node_loads({cohort['block_id']:kw})
            self.assertAlmostEqual(b['ev_kw'],kw)
            self.assertAlmostEqual(a['min_voltage_pu'],b['min_voltage_pu'],places=9)
            self.assertAlmostEqual(sum(s['remaining_kwh'] for s in individual.sessions),cohort['remaining_kwh'],places=8)
            self.assertEqual(sum(x['counts']['connected'] for x in b['blocks']),20)

    def test_different_nodes_deadlines_and_efficiencies_never_merge(self):
        base=dict(id='a',block_id='node-a',arrival_step=0,departure_step=8,energy_kwh=14.,
                  remaining_kwh=14.,delivered_kwh=0.,charger_kw=7.4,efficiency=.9)
        sessions=[base,dict(base,id='b'),dict(base,id='c',block_id='node-b'),
                  dict(base,id='d',departure_step=9),dict(base,id='e',efficiency=.8)]
        groups=aggregate_sessions(sessions)
        self.assertEqual(len(groups),4)
        self.assertEqual(groups[0]['vehicle_count'],2)
        self.assertEqual(sum(s['energy_kwh'] for s in groups),70.)

    def test_random_delay_groups_preserve_release(self):
        base=dict(id='a',block_id='n',arrival_step=0,departure_step=8,energy_kwh=14.,
                  remaining_kwh=14.,delivered_kwh=0.,charger_kw=7.4,delay_jitter=0)
        self.assertEqual(len(aggregate_sessions([base,dict(base,id='b',delay_jitter=1)],True)),2)
