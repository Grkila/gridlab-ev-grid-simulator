import copy
import unittest
from mvgrid.novi_sad.playground_app.server import chart_results


class ChartPayloadTests(unittest.TestCase):
    def test_preserves_electrical_and_service_evidence(self):
        case={'strategy':'immediate','sessions':[{'id':'ev'}], 'metrics':{'unmet_energy_kwh':4},'complete':False,'intervals':[{'step':2,'violations':[{'kind':'overload'}],'ev_kw':7.4,'applied_actions_kw':{'ev':7.4},'blocks':[{'id':'node','counts':{'charging':1},'voltage_pu':.94,'vehicles':[{'id':'ev'}]}]}]}
        original=copy.deepcopy(case)
        result=chart_results({'cases':[case]})['cases'][0]
        self.assertEqual(result['metrics'],original['metrics'])
        self.assertFalse(result['complete'])
        expected=original['intervals'][0]
        expected.pop('applied_actions_kw');expected['blocks'][0].pop('vehicles')
        self.assertEqual(result['intervals'][0],expected)
        self.assertNotIn('sessions',result)

    def test_rl_action_evidence_stays_complete(self):
        case={'strategy':'rl','sessions':[1],'intervals':[{'applied_actions_kw':{'a':1},'blocks':[{'vehicles':[2]}]}]}
        original=copy.deepcopy(case)
        self.assertEqual(chart_results({'cases':[case]})['cases'][0],original)
