import unittest
from math import sqrt

from app.modules.uncertainty.engine import (
    Budget2Resolver,
    Budget2Rule,
    CMCService,
    RSSEngine,
    TypeAProcessor,
    UncertaintyInput,
)


def component(name, value, divisor=1.0, sensitivity=1.0, flow=None):
    return UncertaintyInput(name, "B", "Controlled test", value, "%",
        "Configured", "Controlled", divisor, sensitivity, flow_point=flow)


class UncertaintyEngineTests(unittest.TestCase):
    def test_rss_calculates_intermediate_and_final_values(self):
        result = RSSEngine.calculate((component("one", 3), component("two", 4)), 2)
        self.assertAlmostEqual(result.rss_sum, 25)
        self.assertAlmostEqual(result.combined_standard_uncertainty, 5)
        self.assertAlmostEqual(result.expanded_uncertainty, 10)
        self.assertAlmostEqual(sum(row.contribution_percent for row in result.components), 100)

    def test_input_change_recalculates_rss(self):
        original = RSSEngine.calculate((component("one", 3), component("two", 4)))
        changed = RSSEngine.calculate((component("one", 6), component("two", 4)))
        self.assertNotEqual(original.combined_standard_uncertainty,
                            changed.combined_standard_uncertainty)

    def test_standard_uncertainty_uses_configured_divisor_one(self):
        resolver = Budget2Resolver((Budget2Rule("Standard Uncertainty", "Normal", 1),))
        rule = resolver.resolve("Standard Uncertainty")
        result = RSSEngine.calculate((component("standard", 0.2, rule.divisor),))
        self.assertAlmostEqual(result.components[0].standard_uncertainty, 0.2)

    def test_expanded_uncertainty_uses_recorded_coverage_factor(self):
        resolver = Budget2Resolver((Budget2Rule("Expanded Uncertainty", "Normal", 1, True),))
        rule = resolver.resolve("Expanded Uncertainty", coverage_factor=2.5)
        result = RSSEngine.calculate((component("certificate", 0.25, rule.divisor),))
        self.assertAlmostEqual(result.components[0].standard_uncertainty, 0.1)

    def test_unconfigured_budget2_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            Budget2Resolver(()).resolve("Tolerance")

    def test_type_a_retains_raw_observations_and_statistics(self):
        entry, statistics = TypeAProcessor.from_observations(
            "Repeatability", (10.0, 10.2, 9.8), "L/min", 100, "Manual")
        self.assertEqual(statistics["observations"], (10.0, 10.2, 9.8))
        self.assertEqual(statistics["n"], 3)
        self.assertEqual(entry.degrees_of_freedom, 2)
        self.assertAlmostEqual(entry.input_value,
            statistics["standard_deviation"] / sqrt(3))

    def test_invalid_or_expired_source_cannot_enter_budget(self):
        with self.assertRaisesRegex(ValueError, "not valid"):
            UncertaintyInput("Expired primary", "B", "Equipment Register", 0.2,
                "%", "Standard Uncertainty", "Normal", 1,
                source_status="Expired")

    def test_flow_point_results_are_independent(self):
        low = RSSEngine.calculate((component("primary", 0.1, flow=100),))
        high = RSSEngine.calculate((component("primary", 0.3, flow=500),))
        self.assertNotEqual(low.expanded_uncertainty, high.expanded_uncertainty)

    def test_cmc_models_are_separate_and_supported(self):
        grav = CMCService.calculate("Gravimetric Method", (component("scale", 0.1),))
        coriolis = CMCService.calculate("Coriolis Comparison Method", (component("meter", 0.2),))
        self.assertNotEqual(grav.expanded_uncertainty, coriolis.expanded_uncertainty)
        with self.assertRaises(ValueError):
            CMCService.calculate("Generic", (component("x", 1),))

    def test_snapshot_is_reproducible_and_versioned(self):
        result = RSSEngine.calculate((component("one", 1),))
        snapshot = result.snapshot()
        self.assertEqual(snapshot["calculation_version"], "flp-rss-1.0")
        self.assertEqual(snapshot["components"][0]["input"]["source"], "one")
        self.assertIn("calculated_at", snapshot)


if __name__ == "__main__":
    unittest.main()
