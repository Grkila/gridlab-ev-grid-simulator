"""Persistent workflow and verdict semantics, separate from electrical tests."""
import tempfile
import unittest
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.worker import evaluate


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = Service(self.tmp.name)

    def test_immutable_revision_and_yaml_equivalence(self):
        a = self.service.save_experiment({'name':'test','hypothesis':'Repeatable'})
        b = self.service.save_experiment('name: test\nhypothesis: Repeatable\n')
        self.assertEqual(a,b)
        c = self.service.add_cases(a['experiment_id'], {'seeds':[2,3]})
        self.assertNotEqual(c['experiment_id'],a['experiment_id'])
        self.assertEqual(self.service.get_experiment(a['experiment_id'])['definition']['seeds'],[1])

    def test_bounded_expansion_and_paths(self):
        with self.assertRaises(ValueError):
            self.service.validate_experiment({'name':'test','hypothesis':'bounded','seeds':[1,2], 'max_cases':1})
        with self.assertRaises(ValueError):
            self.service.get_run('../outside')

    def test_hard_failure_is_counterexample_not_partial_success(self):
        config = self.service.validate_experiment({'name':'test','hypothesis':'No overload','assertions':[{'type':'hard','metric':'overload_steps','operator':'le','value':0}]})['definition']
        result={'case_id':'case-1','metrics':{'overload_steps':1}}
        self.assertEqual(evaluate(config,[result],False)['verdict'],'failed')
        self.assertEqual(evaluate(config,[],False)['verdict'],'incomplete')

    def test_paired_requires_full_coverage(self):
        config = self.service.validate_experiment({'name':'test','hypothesis':'Peak reduction','strategies':['immediate','capacity_aware'],'assertions':[{'type':'paired','metric':'peak_demand_kw','reduction_fraction':.1,'control':'immediate','candidate':'capacity_aware'}]})['definition']
        records=[{'case_id':'a','seed':1,'fleet_size':100,'strategy':'immediate','metrics':{'peak_demand_kw':100}}, {'case_id':'b','seed':1,'fleet_size':100,'strategy':'capacity_aware','metrics':{'peak_demand_kw':80}}]
        self.assertEqual(evaluate(config,records,False)['verdict'],'incomplete')
        self.assertEqual(evaluate(config,records,True)['verdict'],'passed')


if __name__=='__main__': unittest.main()
