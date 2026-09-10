import math
import unittest

from pydantic import ValidationError

from mvgrid.novi_sad.playground.demand import allocate_block_demand, generate_demand, generate_sessions
from mvgrid.novi_sad.playground.schema import DemandConfig, Experiment, load_experiment


class PlaygroundSchemaTests(unittest.TestCase):
    def base(self):
        return {"name": "trial", "hypothesis": "delayed charging lowers peak"}

    def test_defaults_and_yaml(self):
        experiment = load_experiment("name: trial\nhypothesis: test\n")
        self.assertEqual(experiment.demand.monthly_energy, 95_636)
        self.assertEqual(experiment.fleet.fleet_size, 100)
        self.assertEqual(experiment.seeds, [1])
        self.assertEqual(experiment.metric_boundary, "city_total")
        self.assertEqual(experiment.observation_contract, "current_state")
        self.assertEqual(experiment.case_origin, "manual")
        self.assertTrue(any("user-supplied" in item for item in experiment.assumptions))

    def test_unknown_and_nonfinite_values_are_rejected(self):
        with self.assertRaises(ValidationError):
            Experiment.model_validate({**self.base(), "surprise": True})
        with self.assertRaises(ValidationError):
            Experiment.model_validate({**self.base(), "fleet": {"charger_kw": math.inf}})
        with self.assertRaises(ValidationError):
            Experiment.model_validate({**self.base(), "demand": {"monthly_energy": math.nan}})

    def test_assertion_shapes_are_typed(self):
        experiment = Experiment.model_validate({**self.base(), "assertions": [
            {"metric": "min_voltage_pu", "operator": "ge", "value": 0.95},
            {"metric": "peak_demand_kw", "reduction_fraction": 0.1,
             "control": "immediate", "candidate": "capacity_aware"},
        ]})
        self.assertEqual(len(experiment.assertions), 2)


class DemandTests(unittest.TestCase):
    def test_growth_compounds_and_preserves_monthly_calibration(self):
        for month, energy, days in ((1, 120000, 31), (6, 76000, 30)):
            with self.subTest(month=month):
                demand = generate_demand(DemandConfig(
                    month=month, monthly_energy=energy, unit="MWh",
                    days_per_month=days, years_ahead=5, days=2,
                ))
                self.assertAlmostEqual(sum(demand) * 0.25,
                                       energy * 1000 / days * 1.03 ** 5 * 2, places=6)

    def test_worst_day_is_twenty_percent_at_every_interval(self):
        for month, energy, days in ((1, 120000, 31), (6, 76000, 30)):
            cfg = DemandConfig(month=month, monthly_energy=energy, days_per_month=days, years_ahead=3)
            base = generate_demand(cfg)
            worst = generate_demand(cfg.model_copy(update={"scenario": "worst_case"}))
            for normal, stressed in zip(base, worst):
                self.assertAlmostEqual(stressed / normal, 1.20)

    def test_growth_and_upper_margin_are_independent(self):
        base = generate_demand(DemandConfig())
        future = generate_demand(DemandConfig(years_ahead=1, variation="upper"))
        self.assertAlmostEqual(sum(future) / sum(base), 1.03 * 1.029)
        unchanged = generate_demand(DemandConfig(years_ahead=20, annual_growth_rate=0))
        self.assertEqual(base, unchanged)

    def test_energy_is_normalized_and_days_repeat(self):
        config = DemandConfig(monthly_energy=30, unit="MWh", days_per_month=30, days=2)
        demand = generate_demand(config)
        self.assertEqual(len(demand), 192)
        self.assertEqual(demand[:96], demand[96:])
        self.assertAlmostEqual(sum(demand[:96]) * 0.25, 1000.0, places=8)

    def test_variation_is_exactly_2_9_percent(self):
        base = generate_demand(DemandConfig(monthly_energy=1, unit="MWh"))
        upper = generate_demand(DemandConfig(monthly_energy=1, unit="MWh", variation="upper"))
        lower = generate_demand(DemandConfig(monthly_energy=1, unit="MWh", variation="lower"))
        self.assertAlmostEqual(sum(upper) / sum(base), 1.029)
        self.assertAlmostEqual(sum(lower) / sum(base), 0.971)

    def test_sessions_are_deterministic_and_may_cross_horizon(self):
        experiment = Experiment(name="trial", hypothesis="test", demand={"days": 1})
        blocks = [{"block_id": "a", "base_weight": 1},
                  {"block_id": "hub", "kind": "public_hub", "base_weight": 0}]
        first = generate_sessions(experiment, blocks, seed=7, fleet_size=100)
        self.assertEqual(first, generate_sessions(experiment, blocks, seed=7, fleet_size=100))
        self.assertTrue(any(item["departure_step"] > 96 for item in first))
        self.assertTrue(all(item["departure_step"] > item["arrival_step"] for item in first))
        self.assertTrue(all(item["block_id"] == "hub" for item in first if item["location_type"] == "public"))
        self.assertTrue(all(item["block_id"] == "a" for item in first if item["location_type"] != "public"))

    def test_sessions_create_one_visit_per_vehicle_per_day(self):
        experiment = Experiment(name="trial", hypothesis="test", demand={"days": 3})
        blocks = [{"id": "load", "base_weight": 1},
                  {"id": "hub", "kind": "public_hub", "base_weight": 0}]
        self.assertEqual(len(generate_sessions(experiment, blocks, seed=2, fleet_size=7)), 21)

    def test_block_allocation_conserves_each_city_interval(self):
        city = [100.0, 120.0, 90.0]
        blocks = [
            {"id": "home", "base_weight": 0.6, "mixture": {"residential": 1}},
            {"id": "shops", "base_weight": 0.4, "mixture": {"commercial": 1}},
            {"id": "hub", "kind": "public_hub", "base_weight": 0},
        ]
        allocated = allocate_block_demand(city, blocks, {"mode": "preserve_city"})
        for step, expected in enumerate(city):
            self.assertAlmostEqual(sum(series[step] for series in allocated.values()), expected)
        self.assertEqual(allocated["hub"], [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
