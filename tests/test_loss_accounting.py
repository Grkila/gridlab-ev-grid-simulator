import math
import unittest
import pandapower as pp
from mvgrid.novi_sad.playground.loss_accounting import reconcile_supply
from mvgrid.novi_sad.playground.simulation import simulate_case


class LossAccountingTests(unittest.TestCase):
    def test_metered_input_contains_baseline_losses_exactly_once(self):
        net=pp.create_empty_network()
        root=pp.create_bus(net,vn_kv=20); bus=pp.create_bus(net,vn_kv=20)
        pp.create_ext_grid(net,root)
        pp.create_line_from_parameters(net,root,bus,length_km=1,r_ohm_per_km=1,x_ohm_per_km=.4,
                                      c_nf_per_km=0,max_i_ka=1)
        idx=pp.create_load(net,bus,p_mw=0)
        blocks=[dict(id='a',load_index=idx)]
        allocation,evidence=reconcile_supply(net,blocks,{'a':[10000.]})
        row=evidence[0]
        self.assertLess(allocation['a'][0],10000.)
        self.assertGreater(row['losses_kw'],0)
        self.assertAlmostEqual(row['load_kw']+row['losses_kw'],10000.,delta=.01)
        p=allocation['a'][0]/1000+1.
        net.load.loc[idx,['p_mw','q_mvar']]=[p,p*math.tan(math.acos(.97))]
        pp.runpp(net,numba=False)
        supply=net.res_ext_grid.p_mw.sum()*1000
        self.assertGreater(supply-10000,1000.)
        # Only the incremental loss is added to the original metered baseline.
        incremental_loss=net.res_line.pl_mw.sum()*1000-row['losses_kw']
        self.assertAlmostEqual(supply-10000,1000+incremental_loss,delta=.01)

    def test_shared_simulator_uses_net_baseline_and_reports_gross_peak(self):
        result=simulate_case({'demand_measurement':'supply_including_losses','stop_on_violation':False},[100000.],[])
        interval=result['intervals'][0]
        self.assertLess(interval['baseline_kw'],100000)
        self.assertAlmostEqual(interval['supply_kw'],100000,delta=.01)
        self.assertAlmostEqual(result['metrics']['peak_demand_kw'],100000,delta=.01)
        self.assertAlmostEqual(interval['incremental_ev_supply_kw'],0,delta=.01)
        self.assertTrue(result['complete'])

    def test_legacy_explicit_load_input_is_preserved(self):
        result=simulate_case({'demand_measurement':'load','stop_on_violation':False},[100000.],[])
        self.assertAlmostEqual(result['intervals'][0]['total_kw'],100000)
        self.assertGreater(result['intervals'][0]['supply_kw'],100000)
        self.assertNotIn('baseline_loss_reconciliation_max_error_kw',result['metrics'])
