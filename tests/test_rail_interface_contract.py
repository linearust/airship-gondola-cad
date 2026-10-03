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

    def test_direct_optical_tray_keeps_the_complete_standard_shoe_and_open_lift_path(
        self,
    ):
        from gondola.parts import optical_mount, rail
        from gondola.validation.rail_access import _lift_path
        from gondola.validation.rail_mount import _literal_protected_mount

        base = optical_mount.rail_mounted_tray_shape()
        region = Part.makeBox(16, 10.5, 12.5, App.Vector(-8, -5.25, 0))
        expected = _literal_protected_mount()
        actual = base.common(region)
        self.assertLess(actual.cut(expected).Volume + expected.cut(actual).Volume, 1e-7)
        report = _lift_path("OpticalSensorTray", base, {"Rail": rail.rail_shape()}, 0)
        self.assertTrue(report["passed"], report)
        # A narrow obstruction inside the shoe's intermediate lift path must
        # fail even when both placement endpoints are clear.
        obstacle = Part.makeBox(1, 1, 1, App.Vector(-0.5, 4, 20))
        self.assertLess(base.common(obstacle).Volume, 1e-7)
        raised = base.copy()
        raised.translate(App.Vector(0, 0, 30))
        self.assertLess(raised.common(obstacle).Volume, 1e-7)
        blocked = _lift_path(
            "OpticalSensorTray",
            base,
            {"Rail": rail.rail_shape(), "Obstacle": obstacle},
            0,
        )
        self.assertFalse(blocked["passed"], blocked)

    def test_direct_optical_tray_trim_covers_all_stock_and_rejects_unknown_stock(self):
        from gondola.parts import optical_mount, rail
        from gondola.validation.rail_access import supported_carrier_slide

        tray = optical_mount.rail_mounted_tray_shape()
        pose = {"attachment_world_axes_x_mm": [140], "expected_carrier_yaw_deg": 180}
        report = supported_carrier_slide(
            {"OpticalSensorTray": tray}, {"Rail": rail.rail_shape()}, pose
        )
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["relative_x_range_mm"], [-3, 3])
        self.assertLess(report["parts"][0]["shape_outside_service_envelope_mm3"], 1e-7)
        extra = Part.makeBox(1, 1, 1, App.Vector(-20, -5.5, 15.5))
        changed = tray.fuse(extra)
        self.assertGreater(changed.Volume - tray.Volume, 0.5)
        bad = supported_carrier_slide(
            {"OpticalSensorTray": changed}, {"Rail": rail.rail_shape()}, pose
        )
        self.assertFalse(bad["passed"])
        self.assertGreater(bad["parts"][0]["shape_outside_service_envelope_mm3"], 0.5)

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

    def test_native_rail_tray_service_retains_sensor_and_rejects_active_stage(self):
        from gondola.cad import set_property
        from gondola.contracts.design import ModuleStation
        from gondola.parts import optical_mount, optical_sensor, rail
        from gondola.validation import baseline, rail_access, rail_interface

        doc = App.newDocument("FixedOpticalTrayRailService")
        self.addCleanup(App.closeDocument, doc.Name)
        mount = optical_mount.build_optical_mount(doc, mode="rail")
        module = mount["group"]
        module.Placement = App.Placement(
            App.Vector(140, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        for name, value, kind in (
            ("RailPositionX", 140, "App::PropertyDistance"),
            ("RailAttachmentOffsetX", 0, "App::PropertyDistance"),
            ("RailAttachmentOffsetsX", [0], "App::PropertyFloatList"),
            ("RailContactLength", 16, "App::PropertyLength"),
        ):
            set_property(module, name, value, kind)
        sensor, _ = optical_sensor.build_sensor(doc, mount["pitch_stage"])
        built_rail = rail.build_rail(doc)
        locks = rail.build_attachment_hardware(doc, module, module.Name)
        registry = doc.addObject("App::FeaturePython", "DesignRegistry")
        for name, objects in (
            ("Modules", [module]),
            ("PrintedParts", mount["printed"] + built_rail["printed"]),
            ("ReferenceParts", sensor),
            ("HardwareParts", locks),
            ("RailLocks", locks),
            ("TapeReferences", built_rail["tapes"]),
        ):
            set_property(registry, name, objects, "App::PropertyLinkList")
        doc.recompute()
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
        with (
            patch.object(
                baseline, "MODULE_STATIONS", (ModuleStation(module.Name, 140, 180),)
            ),
            patch.object(
                rail_interface,
                "MOUNT_BINDINGS",
                (("OpticalSensorTray", module.Name, "optical", 0.0, 16.0),),
            ),
        ):
            report = rail_access.rail_attachment_service(doc, registry, objects)
            self.assertTrue(report["passed"], report)
            row = report["modules"][0]
            self.assertEqual(
                row["removed_attachment_hardware"], sorted(obj.Name for obj in locks)
            )
            self.assertEqual(
                row["populated_module_removal_path_mm"], [(0, 0, 0), (0, 0, 30)]
            )
            self.assertIn(
                sensor[0].Name, [part["part"] for part in row["populated_module_lift"]]
            )
            doc.OpticalPitchStage.MaximumAngle = 20
            doc.recompute()
            with patch.object(rail_access, "world_shape") as geometry:
                invalid = rail_access.rail_attachment_service(doc, registry, objects)
            geometry.assert_not_called()
            self.assertFalse(invalid["passed"])
            self.assertFalse(
                invalid["modules"][0]["required_mount"]["native_mount_frame_matches"]
            )


if __name__ == "__main__":
    unittest.main()
