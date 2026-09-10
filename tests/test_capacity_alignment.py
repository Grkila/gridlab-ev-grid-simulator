"""Check calibration totals, all-city coverage, and electrical-base conversion."""
import unittest
import pandapower as pp
from mvgrid.novi_sad.playground.capacity_alignment import align_delivery_capacity
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.districts import resolve_districts


class CapacityAlignmentTests(unittest.TestCase):
    def test_whole_city_targets_and_planning_budgets(self):
        net, blocks = build_network()
        self.assertEqual(set(net['excluded_sources']), {'NS1','NS6','FUT'})
        self.assertAlmostEqual(net['retained_demand_fraction'], 1.)
        self.assertEqual(len(net.ext_grid), 6)
        self.assertEqual(len({m for b in blocks for m in b['member_ids']}), 2648)
        for voltage, target in ((20, 299.), (10, 179.)):
            self.assertAlmostEqual(float(net.trafo.loc[net.trafo.vn_lv_kv == voltage, 'sn_mva'].sum()) * .97, target)
        districts = resolve_districts(blocks)
        self.assertEqual(len(districts), 10)
        self.assertAlmostEqual(sum(d['capacity_kw'] for d in districts), 478000.)
        self.assertTrue(all('photograph' in d['provenance'] for d in districts))

    def test_removed_sources_have_no_nodes_and_demand_is_reassigned(self):
        net, blocks = build_network()
        self.assertEqual(set(net['excluded_hubs']), {'NS1-HUB','NS6-HUB','FUT-HUB'})
        for name in net.bus['name']:
            self.assertFalse(str(name).startswith(('NS1 ', 'NS1-', 'NS6 ', 'NS6-', 'FUT ', 'FUT-')))
        self.assertEqual(sum(b['kind']=='public_hub' for b in blocks),10)
        reassigned=net['capacity_alignment']['demand_reassignment']['branches']
        self.assertEqual({r['original_source'] for r in reassigned},{'NS1','NS6','FUT'})
        members=[m for r in reassigned for m in r['member_ids']]
        all_members=[m for b in blocks for m in b['member_ids']]
        self.assertEqual(len(members),492)
        self.assertEqual(len(set(all_members)),2648)
        self.assertEqual(len(all_members),2648)
        self.assertTrue(set(members) <= set(all_members))
        self.assertAlmostEqual(net['retained_demand_fraction'],1.)

    def test_removed_districts_cannot_receive_sessions(self):
        from mvgrid.novi_sad.playground.service import Service
        for source in ('NS1','NS6','FUT'):
            with self.assertRaisesRegex(ValueError,'Unknown district IDs'):
                Service().validate_experiment({'name':'placement','hypothesis':'Removed supply',
                    'fleet':{'district_mix':{source:1}}})

    def test_rating_conversion_preserves_power_flow_impedance(self):
        net = pp.create_empty_network()
        hv = pp.create_bus(net, vn_kv=110)
        pp.create_ext_grid(net, hv)
        for voltage in (20, 10):
            lv = pp.create_bus(net, vn_kv=voltage)
            pp.create_transformer_from_parameters(net, hv, lv, sn_mva=50,
                vn_hv_kv=110, vn_lv_kv=voltage, vk_percent=12,
                vkr_percent=.3, pfe_kw=20, i0_percent=.1)
            pp.create_load(net, lv, p_mw=10, q_mvar=2)
        pp.runpp(net, numba=False)
        voltages = net.res_bus.vm_pu.copy()
        power = net.res_ext_grid.p_mw.copy()
        align_delivery_capacity(net)
        pp.runpp(net, numba=False)
        self.assertLess(float((net.res_bus.vm_pu - voltages).abs().max()), 1e-8)
        self.assertLess(float((net.res_ext_grid.p_mw - power).abs().max()), 1e-7)
        with self.assertRaises(ValueError):
            align_delivery_capacity(net)


if __name__ == '__main__':
    unittest.main()
