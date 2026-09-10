import unittest
from mvgrid.novi_sad.playground.operating_scenario import apply_demand_scenario,apply_network_scenario
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.demand import generate_demand
from mvgrid.novi_sad.playground.benchmark import BenchmarkService
import tempfile


class OperatingScenarioTests(unittest.TestCase):
    def test_shift_preserves_each_day_energy_and_reduces_winter_peak(self):
        original=generate_demand(dict(month=1,monthly_energy=120000,days_per_month=31,days=2,scenario='worst_case'))
        revised=apply_demand_scenario(original,'regulated')
        self.assertEqual(max(revised),220000)
        for start in (0,96): self.assertAlmostEqual(sum(original[start:start+96]),sum(revised[start:start+96]),places=6)
        self.assertTrue(any(a>b for a,b in zip(original,revised)))
        self.assertTrue(any(a<b for a,b in zip(original,revised)))

    def test_lower_profile_is_unchanged_and_impossible_cap_is_rejected(self):
        profile=[100000.]*96
        self.assertEqual(apply_demand_scenario(profile,'regulated'),profile)
        with self.assertRaises(ValueError): apply_demand_scenario([230000.]*96,'regulated')
        with self.assertRaises(ValueError): apply_demand_scenario([100000.]*95,'regulated')

    def test_voltage_support_preserves_asset_ratings_and_is_recorded(self):
        net,_=build_network(); ratings=net.trafo.sn_mva.copy(); lines=net.line.max_i_ka.copy()
        apply_network_scenario(net,'regulated')
        self.assertTrue((net.ext_grid.vm_pu==1.04).all())
        self.assertTrue(net.trafo.sn_mva.equals(ratings)); self.assertTrue(net.line.max_i_ka.equals(lines))
        self.assertEqual(net['operating_scenario']['mode'],'regulated')

    def test_scenario_is_frozen_and_not_confused_with_original_suite(self):
        with tempfile.TemporaryDirectory() as root:
            service=BenchmarkService(root)
            cfg=dict(name='Boundary',standard_fleet=1,max_fleet=1,seeds=[41001])
            original=service.create_suite(cfg)
            revised=service.create_suite({**cfg,'operating_mode':'regulated'})
            self.assertNotEqual(original['suite_id'],revised['suite_id'])
            self.assertEqual(service.get_suite(revised['suite_id'])['config']['operating_mode'],'regulated')
