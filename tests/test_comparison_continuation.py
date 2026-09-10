"""Independent batch-control checks using frozen tiny replay manifests.

The simulation is replaced at its boundary: these checks test orchestration,
not electrical validity (covered separately by the monitoring suite).
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mvgrid.novi_sad.playground.schema import Experiment
from mvgrid.novi_sad.playground.service import cases_for, read_json, write_json
from mvgrid.novi_sad.playground.worker import run


class ComparisonContinuationTests(unittest.TestCase):
    def execute(self, outcomes, strategies=None, assertions=None, **overrides):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        folder = root / 'runs' / 'run-test'
        config = Experiment(name='Batch isolation', hypothesis='Each strategy is attempted',
                            strategies=strategies or ['immediate', 'capacity_aware'],
                            assertions=assertions or [], **overrides).model_dump(mode='json')
        cases = cases_for(config)
        write_json(root / 'experiments' / 'exp-test.json', {'definition': config})
        write_json(folder / 'state.json', {'pid': 123, 'experiment_id': 'exp-test'})
        write_json(folder / 'manifest.json', {
            'definition': config, 'cases': cases, 'demand_kw': [10, 10],
            'blocks': [{'id': 'block', 'base_weight': 1}], 'resolved_districts': [],
            'replays': {f"{c['seed']}-{c['fleet_size']}": [] for c in cases},
        })
        (root / 'worker.lock').write_text('run-test', encoding='utf-8')
        with patch('mvgrid.novi_sad.playground.worker.simulate_case', side_effect=outcomes) as simulate:
            run(str(root), 'run-test')
        records = [read_json(p) for p in sorted((folder / 'cases').glob('*.json'))]
        assessment = read_json(folder / 'evaluation.json') if (folder / 'evaluation.json').exists() else None
        self.assertFalse((root / 'worker.lock').exists())
        return simulate.call_count, read_json(folder / 'state.json'), records, assessment

    @staticmethod
    def completed(peak=10):
        return {'complete': True, 'metrics': {'peak_demand_kw': peak, 'unmet_energy_kwh': peak}, 'intervals': [], 'sessions': []}

    @staticmethod
    def stopped():
        return {'complete': False, 'metrics': {'peak_demand_kw': 20}, 'intervals': [], 'sessions': [],
                'stop_reason': {'step': 0, 'violations': [{'kind': 'transformer_overload'}]}}

    def test_limit_stop_does_not_skip_comparison_peer(self):
        calls, state, records, assessment = self.execute([self.stopped(), self.completed()])
        self.assertEqual(calls, 2)
        self.assertEqual(len(records), 2)
        self.assertEqual(state['completed_cases'], 2)
        self.assertFalse(assessment['complete'])
        self.assertEqual(assessment['verdict'], 'incomplete')

    def test_controller_exception_is_saved_and_peer_runs(self):
        calls, state, records, assessment = self.execute([ValueError('controller broke'), self.completed()])
        self.assertEqual(calls, 2)
        self.assertEqual(len(records), 2)
        failed = next(r for r in records if r['strategy'] == 'immediate')
        self.assertFalse(failed['complete'])
        self.assertIn('controller broke', str(failed))
        self.assertEqual(assessment['verdict'], 'incomplete')

    def test_stress_counterexample_does_not_skip_comparison_peer(self):
        calls, state, records, assessment = self.execute(
            [self.completed(20), self.completed(8)], stress_first=True,
            assertions=[{'type': 'hard', 'metric': 'unmet_energy_kwh', 'operator': 'le', 'value': 10}])
        self.assertEqual(calls, 2)
        self.assertTrue(assessment['complete'])
        self.assertEqual(assessment['verdict'], 'failed')

    def test_partial_pair_cannot_claim_reduction_pass(self):
        calls, state, records, assessment = self.execute(
            [self.stopped(), self.completed(1)],
            assertions=[{'type': 'paired', 'metric': 'peak_demand_kw', 'control': 'immediate',
                         'candidate': 'capacity_aware', 'reduction_fraction': .1}])
        self.assertEqual(calls, 2)
        self.assertEqual(assessment['verdict'], 'incomplete')
        self.assertEqual(assessment['assertions'][0]['verdict'], 'incomplete')

    def test_cancellation_still_stops_entire_batch(self):
        calls, state, _, _ = self.execute([InterruptedError('cancelled'), self.completed()])
        self.assertEqual(calls, 1)
        self.assertEqual(state['status'], 'cancelled')

    def test_budget_still_stops_entire_batch(self):
        calls, state, _, _ = self.execute([TimeoutError('budget_exceeded'), self.completed()])
        self.assertEqual(calls, 1)
        self.assertEqual(state['status'], 'budget_exceeded')

    def test_single_strategy_still_stops_on_limit(self):
        calls, state, records, assessment = self.execute(
            [self.stopped(), self.completed()], strategies=['immediate'], seeds=[1, 2])
        self.assertEqual(calls, 1)
        self.assertEqual(state['status'], 'stopped_on_violation')
        self.assertFalse(assessment['complete'])

    def test_single_strategy_stress_rejection_is_preserved(self):
        calls, state, records, assessment = self.execute(
            [self.completed(20), self.completed()], strategies=['immediate'], seeds=[1, 2],
            stress_first=True,
            assertions=[{'type': 'hard', 'metric': 'unmet_energy_kwh', 'operator': 'le', 'value': 10}])
        self.assertEqual(calls, 1)
        self.assertEqual(state['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()

