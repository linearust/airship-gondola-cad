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

    def test_instrument_base_keeps_complete_standard_shoe_and_open_lift(self):
        from gondola.parts import instrument_mount, rail
        from gondola.validation.rail_access import _lift_path
        from gondola.validation.rail_mount import _literal_protected_mount

        base = instrument_mount.base_shape()
        region = Part.makeBox(16, 10.5, 12.5, App.Vector(-8, -5.25, 0))
        expected, actual = _literal_protected_mount(), base.common(region)
        self.assertLess(actual.cut(expected).Volume + expected.cut(actual).Volume, 1e-7)
        self.assertTrue(
            _lift_path("InstrumentMountBase", base, {"Rail": rail.rail_shape()}, 0)[
                "passed"
            ]
        )
        obstacle = Part.makeBox(1, 1, 1, App.Vector(-0.5, 2, 20))
        self.assertLess(base.common(obstacle).Volume, 1e-7)
        raised = base.copy()
        raised.translate(App.Vector(0, 0, 30))
        self.assertLess(raised.common(obstacle).Volume, 1e-7)
        blocked = _lift_path(
            "InstrumentMountBase",
            base,
            {"Rail": rail.rail_shape(), "Obstacle": obstacle},
            0,
        )
        self.assertFalse(blocked["passed"], blocked)

    def test_instrument_base_trim_rejects_unknown_stock_beside_standard_legs(self):
        from gondola.parts import instrument_mount, rail
        from gondola.validation.rail_access import supported_carrier_slide

        base = instrument_mount.base_shape()
        pose = {"attachment_world_axes_x_mm": [-84], "expected_carrier_yaw_deg": 180}
        report = supported_carrier_slide(
            {"InstrumentMountBase": base}, {"Rail": rail.rail_shape()}, pose
        )
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["relative_x_range_mm"], [-3, 3])
        changed = base.fuse(Part.makeBox(3, 1, 1, App.Vector(4, 4, 6))).removeSplitter()
        self.assertEqual(len(changed.Solids), 1)
        bad = supported_carrier_slide(
            {"InstrumentMountBase": changed}, {"Rail": rail.rail_shape()}, pose
        )
        self.assertFalse(bad["passed"])
        self.assertGreater(bad["parts"][0]["shape_outside_service_envelope_mm3"], 1.9)

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

    def test_native_instrument_rail_service_retains_fc_optics_and_rejects_displaced_base(
        self,
    ):
        from gondola.config import BASELINE_FILE
        from gondola.validation import rail_access

        doc = App.openDocument(str(BASELINE_FILE), hidden=True)
        self.addCleanup(App.closeDocument, doc.Name)
        registry = doc.DesignRegistry
        objects = [
            obj
            for key in (
                "PrintedParts",
                "ReferenceParts",
                "HardwareParts",
                "TapeReferences",
            )
            for obj in getattr(registry, key)
        ]
        report = rail_access.rail_attachment_service(
            doc, registry, objects, module_names=("ElectronicsEquipmentModule",)
        )
        self.assertTrue(report["passed"], report)
        row = report["modules"][0]
        carried = {part["part"] for part in row["populated_module_lift"]}
        self.assertTrue(
            {
                "InstrumentMountBase",
                "ElectronicsMount",
                "ModuleFCEnvelope",
                "ModuleMTF02PEnvelope",
            }.issubset(carried)
        )
        doc.InstrumentMountBase.Placement.Base.x = 1
        with patch.object(rail_access, "world_shape") as geometry:
            invalid = rail_access.rail_attachment_service(
                doc, registry, objects, module_names=("ElectronicsEquipmentModule",)
            )
        geometry.assert_not_called()
        self.assertFalse(invalid["passed"])
        self.assertFalse(
            invalid["modules"][0]["required_mount"]["native_mount_frame_matches"]
        )


if __name__ == "__main__":
    unittest.main()
