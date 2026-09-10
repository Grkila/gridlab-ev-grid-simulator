"""Black-box checks that district estimates remain independent planning inputs."""

import unittest
import tempfile

from mvgrid.novi_sad.playground.network import build_network
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.service import write_json
from mvgrid.novi_sad.playground.simulation import simulate_case


class IndependentDistrictContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.blocks = build_network()

    def test_demand_growth_does_not_recalculate_capacity_estimates(self):
        base = {
            "name": "capacity independence",
            "hypothesis": "Demand changes do not redefine district capacity.",
            "demand": {
                "monthly_energy": 95_636,
                "annual_growth_rate": 0.0,
                "years_ahead": 0,
            },
        }
        stressed = {
            **base,
            "demand": {
                **base["demand"],
                "monthly_energy": 180_000,
                "annual_growth_rate": 0.07,
                "years_ahead": 12,
            },
        }

        with tempfile.TemporaryDirectory() as home:
            service = Service(home)
            first = service.validate_experiment(base)["resolved_districts"]
            second = service.validate_experiment(stressed)["resolved_districts"]

        self.assertEqual(
            [(d["id"], d["capacity_kw"], d["provenance"]) for d in first],
            [(d["id"], d["capacity_kw"], d["provenance"]) for d in second],
        )

    def test_separate_district_budgets_do_not_mask_shared_upstream_overload(self):
        # CENTAR and IND are separate published delivery groups behind NS2.  Each
        # is held below its own central estimate while their coincident demand
        # crosses the shared 110/35-kV transformer boundary.
        profiles = {block["id"]: [0.0] for block in self.blocks}
        for district_id in ("CENTAR", "IND"):
            members = [
                block for block in self.blocks if block["delivery_id"] == district_id
            ]
            for block in members:
                profiles[block["id"]] = [24_000 / len(members)]

        result = simulate_case(
            {"block_demand_kw": profiles, "stop_on_violation": False},
            [48_000],
            [],
        )
        interval = result["intervals"][0]
        selected = {
            district["id"]: district
            for district in interval["districts"]
            if district["id"] in {"CENTAR", "IND"}
        }

        self.assertEqual(set(selected), {"CENTAR", "IND"})
        self.assertTrue(
            all(d["total_kw"] < d["capacity_kw"] for d in selected.values())
        )
        self.assertFalse(
            any(
                violation["kind"] == "district_capacity_exceeded"
                for violation in interval["violations"]
            )
        )
        upstream = [
            violation
            for violation in interval["violations"]
            if violation["kind"] == "transformer_overload"
            and violation["asset_id"] == "NS2 110/35 kV"
        ]
        self.assertTrue(upstream)
        self.assertGreater(upstream[0]["value"], upstream[0]["limit"])

    def test_capacity_revision_is_not_a_paired_controller_comparison(self):
        with tempfile.TemporaryDirectory() as home:
            service = Service(home)
            common = {
                "name": "paired boundary",
                "hypothesis": "Only controller choice changes.",
                "strategies": ["immediate"],
            }
            experiments = [
                service.save_experiment(common),
                service.save_experiment(
                    {
                        **common,
                        "district_capacity": {
                            "scenario": "high",
                            "overrides": {},
                        },
                    }
                ),
            ]
            for index, experiment in enumerate(experiments):
                run_id = f"run-contract-{index}"
                folder = service.root / "runs" / run_id
                write_json(
                    folder / "state.json",
                    {
                        "run_id": run_id,
                        "experiment_id": experiment["experiment_id"],
                        "status": "completed",
                    },
                )
                write_json(folder / "manifest.json", {"fingerprint": {"same": True}})
                write_json(folder / "evaluation.json", {"complete": True})
                write_json(
                    folder / "cases" / "case-0000.json",
                    {
                        "case_id": "case-0000",
                        "strategy": "immediate",
                        "seed": 1,
                        "fleet_size": 100,
                        "metrics": {"peak_demand_kw": 1},
                        "complete": True,
                    },
                )

            comparison = service.compare_runs(
                ["run-contract-0", "run-contract-1"]
            )
            self.assertTrue(comparison["complete"])
            self.assertIn("district_capacity", comparison["differing_fields"])
            self.assertFalse(comparison["paired_compatible"])


if __name__ == "__main__":
    unittest.main()
