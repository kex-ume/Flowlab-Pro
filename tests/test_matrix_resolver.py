import unittest

from app.modules.uncertainty.engine import RSSEngine, UncertaintyInput
from app.modules.uncertainty.matrix import MatrixBand, MatrixResolver


def band(low, high, suffix):
    return MatrixBand(low, high, f"P{suffix}", f"T{suffix}", f"DIV-{suffix}",
        f"WS-{suffix}", f"MM-{suffix}", f"TT-{suffix}", f"PT-{suffix}",
        f"Procedure {suffix}")


def result(value):
    source = UncertaintyInput("source", "B", "test", value, "%",
        "Standard Uc", "Normal", 1)
    return RSSEngine.calculate((source,))


class MatrixResolverTests(unittest.TestCase):
    def setUp(self):
        self.bands = (band(0, 30, 1), band(31, 100, 2), band(101, 400, 3))

    def test_point_resolves_equipment_identity(self):
        match = MatrixResolver.resolve_point(self.bands, 75, "L/min")
        self.assertEqual(match.reference_meter, "MM-2")
        self.assertEqual(match.weighing_system, "WS-2")

    def test_wide_range_returns_every_overlapping_band(self):
        matches = MatrixResolver.resolve_range(self.bands, 20, 200, "L/min")
        self.assertEqual([item.reference_meter for item in matches], ["MM-1", "MM-2", "MM-3"])

    def test_m3_per_hour_uses_same_normalized_model(self):
        match = MatrixResolver.resolve_point(self.bands, 4.5, "m³/h")
        self.assertEqual(match.reference_meter, "MM-2")

    def test_out_of_range_and_invalid_range_are_rejected(self):
        with self.assertRaises(ValueError):
            MatrixResolver.resolve_range(self.bands, 0, 500, "L/min")
        with self.assertRaises(ValueError):
            MatrixResolver.resolve_range(self.bands, 100, 50, "L/min")

if __name__ == "__main__":
    unittest.main()
