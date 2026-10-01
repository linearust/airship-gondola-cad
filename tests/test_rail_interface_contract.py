"""The replaceable servo saddle cannot redefine the fixed output-frame interface."""

import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SharedRailInterfaceTests(unittest.TestCase):
    def test_frame_geometry_metadata_and_probes_do_not_follow_bridge_implementation(
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
        with (
            patch.multiple(
                servo_bridge,
                SEAT_Z=99,
                CENTRAL_SEAT_LENGTH=123,
                CENTRAL_SEAT_WIDTH=321,
                CHEEK_CONTACT_Y=-30,
                CONNECTOR_PLATE_BOTTOM_Z=80,
            ),
            patch.object(
                servo_bridge,
                "cut_shared_bolt_passage",
                side_effect=AssertionError("Frame called replaceable saddle cutter"),
            ),
        ):
            replacement = propulsion._build_frame(
                doc, replacement_parent, SELECTED_DRIVE
            )
            replacement_probes = [
                row
                for row in propulsion.manufacturing_wall_probes()
                if row[1] == "PropulsionFixedFrame"
            ]
        self.assertEqual(original_probes, replacement_probes)
        self.assertTrue(compare_shape_objects(replacement, original)["passed"])
        for name in ("CentralBridgeSeatZ", "FootBottomZ", "RailContactLength"):
            self.assertEqual(getattr(original, name), getattr(replacement, name))

    def test_legacy_bridge_cutter_keeps_the_same_closed_shared_passages(self):
        from gondola.parts import rail, servo_bridge
        from gondola.print_export import geometry_comparison

        stock = Part.makeBox(46, 22, 11, App.Vector(-23, -11, 1.5))
        actual = servo_bridge.cut_shared_bolt_passage(stock)
        expected = stock
        for x in (-15, 15):
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
