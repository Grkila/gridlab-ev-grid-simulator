import unittest
from unittest.mock import patch
import pandapower as pp
from pandapower.powerflow import LoadflowNotConverged
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.simulation import simulate_case, Simulator


class PlaygroundSimulationTests(unittest.TestCase):
    def test_hand_checkable_single_line_flow(self):
        net=pp.create_empty_network()
        source=pp.create_bus(net,vn_kv=20)
        sink=pp.create_bus(net,vn_kv=20)
        pp.create_ext_grid(net,source,vm_pu=1.)
        pp.create_line_from_parameters(net,source,sink,length_km=1,r_ohm_per_km=.1,x_ohm_per_km=.1,c_nf_per_km=0,max_i_ka=1)
        pp.create_load(net,sink,p_mw=1,q_mvar=0)
        pp.runpp(net,numba=False)
        # Three-phase first-order voltage drop R*P/Vll^2 = .00025 pu.
        self.assertAlmostEqual(net.res_bus.at[sink,'vm_pu'],.99975,delta=1e-6)
        self.assertAlmostEqual(net.res_line.at[0,'i_ka'],1/(3**.5*20),delta=1e-5)
        self.assertAlmostEqual(net.res_ext_grid.p_mw.sum(),net.res_load.p_mw.sum()+net.res_line.pl_mw.sum(),places=7)

    def test_reduction_preserves_reference(self):
        net,blocks=build_network()
        self.assertEqual(len(net.ext_grid),6)
        self.assertEqual(len(blocks),52)
        self.assertEqual(sum(len(b['member_ids']) for b in blocks),2648)
        self.assertAlmostEqual(sum(b['base_weight'] for b in blocks),1)
        self.assertAlmostEqual(sum(b['base_kw'] for b in blocks),214854*net.retained_demand_fraction,delta=1)

    def test_electrical_hierarchy_and_exclusions(self):
        net,blocks=build_network()
        self.assertEqual({b['source_id'] for b in blocks},{'NS2','NS4','NS5','NS7','NS9','RIM'})
        self.assertEqual(len(net.trafo),12)
        self.assertTrue(any(b['delivery_voltage_kv']==10 for b in blocks))
        for block in blocks:
            self.assertEqual(block['path_bus_indices'][0],block['source_bus_index'])
            self.assertEqual(block['path_bus_indices'][-1],block['bus_index'])
            self.assertIn(block['trafo_index'],block['path_trafo_indices'])
            if block['delivery_voltage_kv']==10:
                self.assertEqual(len(block['path_trafo_indices']),2)
                self.assertEqual(len(block['upstream_line_indices']),1)
        members=[x for b in blocks for x in b['member_ids']]
        self.assertEqual(len(members),len(set(members)))

    def test_energy_and_departure(self):
        _,blocks=build_network()
        session=dict(id='a',block_id=blocks[0]['id'],arrival_step=0,departure_step=2,energy_kwh=20,charger_kw=10,efficiency=.8)
        result=simulate_case({},[10000]*2,[session])
        self.assertAlmostEqual(result['metrics']['delivered_energy_kwh'],4)
        self.assertAlmostEqual(result['metrics']['grid_ev_energy_kwh'],5)
        self.assertAlmostEqual(result['metrics']['unmet_energy_kwh'],16)
        self.assertEqual(result['intervals'][-1]['blocks'][0]['counts']['departed_shortfall'],1)
        self.assertNotIn('remaining_kwh',session)

    def test_replay_and_order(self):
        _,blocks=build_network()
        sessions=[dict(id='a',block_id=blocks[0]['id'],arrival_step=0,departure_step=3,energy_kwh=2,charger_kw=11,efficiency=.9)]
        a=simulate_case({'strategy':'randomized_delay','seed':4,'fixed_start_hour':0},[10000]*3,sessions)
        simulate_case({'strategy':'immediate'},[10000]*3,sessions)
        b=simulate_case({'strategy':'randomized_delay','seed':4,'fixed_start_hour':0},[10000]*3,sessions)
        self.assertEqual(a['intervals'],b['intervals'])

    def test_nonconvergence_is_not_success(self):
        with patch('mvgrid.novi_sad.playground.simulation.pp.runpp',side_effect=LoadflowNotConverged()):
            r=simulate_case({},[10000],[])
        self.assertEqual(r['metrics']['nonconverged_steps'],1)
        self.assertIsNone(r['metrics']['min_voltage_pu'])
        self.assertEqual(r['intervals'][0]['violations'][0]['kind'],'nonconvergence')

    def test_overload_and_voltage_observable(self):
        r=simulate_case({},[400000],[])
        self.assertTrue(r['metrics']['overload_steps'] or r['metrics']['nonconverged_steps'])
        self.assertTrue(r['metrics']['voltage_violation_steps'] or r['metrics']['nonconverged_steps'])

    def test_custom_block_profile_and_capacity_control(self):
        _,blocks=build_network()
        profile={b['id']:[0.] for b in blocks}
        hub=next(b for b in blocks if b.get('kind')=='public_hub')
        profile[hub['id']]=[100.]
        sessions=[dict(id='hub',block_id=hub['id'],arrival_step=0,departure_step=1,energy_kwh=2000,charger_kw=10000,efficiency=1)]
        uncontrolled=simulate_case({'block_demand_kw':profile},[100.],sessions)
        self.assertGreater(uncontrolled['metrics']['max_line_loading_percent'],100)
        controlled=simulate_case({'strategy':'capacity_aware','block_demand_kw':profile},[100.],sessions)
        self.assertLessEqual(controlled['metrics']['max_line_loading_percent'],100)
        self.assertGreater(controlled['intervals'][0]['curtailed_ev_kw'],0)
        self.assertEqual(controlled['intervals'][0]['baseline_kw'],100)
        self.assertGreater(controlled['metrics']['unmet_energy_kwh'],0)

    def test_overnight_and_step(self):
        _,blocks=build_network()
        sim=Simulator()
        sim.reset({},[1000]*98,[dict(id='a',block_id=blocks[0]['id'],arrival_step=95,departure_step=98,energy_kwh=3,charger_kw=4,efficiency=1)])
        # The same step API accepts externally supplied actions for future policies.
        for _ in range(98): sim.step({'a':4})
        self.assertAlmostEqual(sim.sessions[0]['delivered_kwh'],3)
        self.assertTrue(sim.observation()['done'])

if __name__=='__main__': unittest.main()
