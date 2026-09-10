import unittest
import pandapower as pp
from mvgrid.novi_sad.playground.feeder_equivalent import worst_path_equivalent


class FeederEquivalentTests(unittest.TestCase):
    def test_two_independent_equal_branches_do_not_each_carry_total_load(self):
        z, _ = worst_path_equivalent({'a':[1], 'b':[2]}, {'a':1.,'b':1.}, {1:1+.4j,2:1+.4j})
        self.assertAlmostEqual(z, .5+.2j)

    def test_shared_trunk_carries_both_loads_and_weak_path_is_preserved(self):
        z, member = worst_path_equivalent({'a':[0,1], 'b':[0,2]}, {'a':3.,'b':1.},
                                          {0:.2+.1j,1:.4+.2j,2:2+1j})
        self.assertEqual(member, 'b')
        self.assertAlmostEqual(z, .7+.35j)

    def test_invariant_to_power_units_and_single_series_path(self):
        for scale in (1,1000):
            z, _ = worst_path_equivalent({'a':[0,1]}, {'a':scale}, {0:.2+.1j,1:.4+.2j})
            self.assertAlmostEqual(z,.6+.3j)

    def test_equivalent_matches_equal_branch_ac_voltages(self):
        full = pp.create_empty_network()
        root = pp.create_bus(full,vn_kv=20)
        pp.create_ext_grid(full,root)
        for _ in range(2):
            bus = pp.create_bus(full,vn_kv=20)
            pp.create_line_from_parameters(full,root,bus,length_km=1,r_ohm_per_km=1,
                                           x_ohm_per_km=.4,c_nf_per_km=0,max_i_ka=1)
            pp.create_load(full,bus,p_mw=1,q_mvar=.25)
        pp.runpp(full,numba=False)
        reduced = pp.create_empty_network()
        root = pp.create_bus(reduced,vn_kv=20); bus=pp.create_bus(reduced,vn_kv=20)
        pp.create_ext_grid(reduced,root)
        z,_ = worst_path_equivalent({'a':[0],'b':[1]},{'a':1.,'b':1.},{0:1+.4j,1:1+.4j})
        pp.create_line_from_parameters(reduced,root,bus,length_km=1,r_ohm_per_km=z.real,
                                      x_ohm_per_km=z.imag,c_nf_per_km=0,max_i_ka=2)
        pp.create_load(reduced,bus,p_mw=2,q_mvar=.5)
        pp.runpp(reduced,numba=False)
        self.assertAlmostEqual(full.res_bus.vm_pu.min(),reduced.res_bus.vm_pu.min(),places=9)
        self.assertAlmostEqual(full.res_line.pl_mw.sum(),reduced.res_line.pl_mw.sum(),places=9)

    def test_invalid_inputs_rejected(self):
        with self.assertRaises(ValueError): worst_path_equivalent({'a':[]},{'a':0},{})
        with self.assertRaises(ValueError): worst_path_equivalent({'a':[0]},{'a':1},{0:complex(float('nan'),0)})
