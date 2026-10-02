"""Servo geometry cannot redefine the independent rail attachment interface."""

import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SharedRailInterfaceTests(unittest.TestCase):
    def test_cradle_case_allowance_does_not_redefine_the_rail_interface(
        self,
    ):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts import propulsion, servo_bridge
        from gondola.validation.baseline import compare_shape_objects

        doc = App.newDocument("IndependentSharedRailInterface")
        self.addCleanup(App.closeDocument, doc.Name)
        original_parent = doc.addObject("App::Part", "Original")
        original = propulsion._build_frame(doc, original_parent, SELECTED_DRIVE)
        original_probes = [
            row
            for row in propulsion.manufacturing_wall_probes()
            if row[1] == "PropulsionFixedFrame"
        ]
        replacement_parent = doc.addObject("App::Part", "Replacement")
        with patch.object(servo_bridge, "CASE_WINDOW_WIDTH", 7.8):
            replacement = propulsion._build_frame(
                doc, replacement_parent, SELECTED_DRIVE
            )
            replacement_probes = [
                row
                for row in propulsion.manufacturing_wall_probes()
                if row[1] == "PropulsionFixedFrame"
            ]
        self.assertEqual(original_probes, replacement_probes)
        self.assertFalse(compare_shape_objects(replacement, original)["passed"])
        # A larger servo clearance changes only the cradle. The entire rail
        # contact stock below Z15 retains exactly the same saved geometry.
        lower = Part.makeBox(60, 100, 15, App.Vector(-30, -50, 0))
        first, second = original.Shape.common(lower), replacement.Shape.common(lower)
        self.assertLess(first.cut(second).Volume + second.cut(first).Volume, 1e-7)
        for name in ("CentralBridgeSeatZ", "FootBottomZ", "RailContactLength"):
            self.assertEqual(getattr(original, name), getattr(replacement, name))

    def test_both_shoes_share_the_same_closed_m3_passages(self):
        from gondola.parts import rail
        from gondola.print_export import geometry_comparison

        stock = Part.makeBox(44, 10.5, 10, App.Vector(-22, -5.25, 2.5))
        actual = rail.cut_shared_bolt_passage(stock)
        expected = stock
        for x in (-14, 14):
            expected = expected.cut(
                Part.makeCylinder(1.7, 24, App.Vector(x, -12, 6), App.Vector(0, 1, 0))
            )
        self.assertLess(geometry_comparison(actual, expected)["difference_mm3"], 1e-7)
        self.assertLess(
            geometry_comparison(actual, rail.cut_shared_bolt_passage(stock))[
                "difference_mm3"
            ],
            1e-7,
        )


if __name__ == "__main__":
    unittest.main()
