"""Reserve is usable; sequential stage capacities are never summed as supply."""
import unittest
from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.capacity_layers import capacity_layers
from mvgrid.novi_sad.playground.simulation import simulate_case
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.worker import evaluate


class CapacityLayerTests(unittest.TestCase):
    def test_inventory_and_nonduplicated_flow(self):
        net, blocks = build_network()
        baseline = {b['id']: 150000*b['base_weight'] for b in blocks}
        ev = {b['id']: 0. for b in blocks}
        rows = {r['id']:r for r in capacity_layers(net,blocks,baseline,ev,supply_kw=152000)}
        self.assertAlmostEqual(sum(r['rating_kw'] for r in rows.values()),1178000)
        self.assertAlmostEqual(rows['mv_20']['demand_kw']+rows['mv_10']['demand_kw'],150000)
        self.assertEqual(rows['transmission']['demand_kw'],152000)
        self.assertAlmostEqual(rows['lv_network']['demand_kw'],75000)
        self.assertEqual(rows['lv_network']['demand_kw'],rows['lv_transformers']['demand_kw'])
        self.assertEqual(rows['lv_network']['capacity_kw'],120000)

    def test_reserve_is_usable_but_full_rating_stops(self):
        options={'network_capacity':{'lv_baseline_fraction':1.,'lv_ev_fraction':1.}}
        safe=simulate_case(options,[100000],[])
        self.assertTrue(safe['complete'])
        row=next(r for r in safe['intervals'][0]['capacity_layers'] if r['id']=='lv_network')
        self.assertAlmostEqual(row['reserve_used_kw'],10000)
        self.assertAlmostEqual(row['headroom_kw'],20000)
        over=simulate_case(options,[120001,120001],[])
        self.assertFalse(over['complete'])
        self.assertEqual(over['metrics']['network_capacity_overload_steps'],1)
        event=next(v for v in over['intervals'][0]['violations'] if v['asset_id']=='lv_network')
        self.assertEqual(event['limit'],120000)
        over['case_id']='over'
        verdict=evaluate({'assertions':[{'type':'hard','metric':'network_capacity_overload_steps','operator':'le','value':0}]},[over],False)
        self.assertEqual(verdict['verdict'],'failed')
        self.assertTrue(verdict['assertions'][0]['counterexamples'][0]['first_interval'])

    def test_controller_can_charge_in_reserve_and_obeys_lv_limit(self):
        _,blocks=build_network()
        sessions=[dict(id=b['id'],block_id=b['id'],arrival_step=0,departure_step=1,
                       energy_kwh=100,charger_kw=400,efficiency=1.) for b in blocks]
        result=simulate_case({'strategy':'capacity_aware','network_capacity':{'lv_baseline_fraction':1.}},[110000],sessions)
        interval=result['intervals'][0]
        self.assertGreater(interval['ev_kw'],0)
        self.assertLessEqual(interval['total_kw'],120000+1e-6)
        self.assertEqual(result['metrics']['network_capacity_overload_steps'],0)
        row=next(r for r in interval['capacity_layers'] if r['id']=='lv_network')
        self.assertGreater(row['reserve_used_kw'],0)

    def test_fraction_inputs_are_validated(self):
        for value in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):
                Service().validate_experiment({'name':'invalid','hypothesis':'Reject invalid shares','network_capacity':{'lv_baseline_fraction':value}})

    def test_historical_network_does_not_gain_new_verdict(self):
        net,blocks=build_network()
        net['capacity_alignment'].pop('operating_model')
        zeros={b['id']:0. for b in blocks}
        self.assertEqual(capacity_layers(net,blocks,zeros,zeros),[])


if __name__=='__main__':
    unittest.main()
