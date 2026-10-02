"""Continuous carrier adjustment with complete carried and retained geometry."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class CarrierTrimTests(unittest.TestCase):
    def test_local_contact_interval_reverses_with_yaw(self):
        from gondola.validation.rail_access import _carrier_trim_interval

        for axis, yaw, expected in (
            (0, 0, (-3, 3)),
            (-140, 0, (-3, 3)),
            (-140, 180, (-3, 3)),
            (140, 0, (-3, 3)),
            (140, 180, (-3, 3)),
            (143, 0, (-6, 0)),
            (-55.5, 180, (-2.5, 3.5)),
        ):
            with self.subTest(axis=axis, yaw=yaw):
                result = _carrier_trim_interval(
                    {
                        "attachment_world_axes_x_mm": [axis],
                        "expected_carrier_yaw_deg": yaw,
                    }
                )
                for actual, target in zip(result, expected):
                    self.assertAlmostEqual(actual, target)
        for axes, yaw in (([], 0), ([0, 28], 0), ([4], 0), ([143.01], 0), ([0], 90)):
            with self.subTest(axes=axes, yaw=yaw), self.assertRaises(ValueError):
                _carrier_trim_interval(
                    {
                        "attachment_world_axes_x_mm": axes,
                        "expected_carrier_yaw_deg": yaw,
                    }
                )

    def test_carried_device_hits_midpath_obstacle_with_both_endpoints_clear(self):
        from gondola.cad import translated_shape
        from gondola.validation.rail_access import supported_carrier_slide

        carried = Part.makeBox(0.1, 1, 1)
        obstacle = Part.makeBox(0.1, 1, 1, App.Vector(0.4, 0, 0))
        for dx in (-3, 3):
            self.assertLess(
                translated_shape(carried, x=dx).common(obstacle).Volume, 1e-7
            )
        result = supported_carrier_slide(
            {"CarriedBoard": carried},
            {"Neighbour": obstacle},
            {"attachment_world_axes_x_mm": [0], "expected_carrier_yaw_deg": 0},
        )
        self.assertFalse(result["passed"])
        self.assertGreater(
            result["parts"][0]["segments"][0]["intersection_mm3"]["Neighbour"], 0
        )

    def test_actual_carrier_and_hardware_clear_rail_and_tape_continuously(self):
        from gondola.cad import union
        from gondola.parts import equipment_mounts, rail
        from gondola.validation.rail_access import supported_carrier_slide

        carrier = equipment_mounts.mount_shape("accessory")
        shapes = {
            "AccessoryMount": carrier,
            "AccessoryEquipmentModuleRailMountScrew": rail.attachment_screw_shape(),
            "AccessoryEquipmentModuleRailMountNut": rail.nut_shape(),
        }
        obstacles = {
            "Rail": rail.rail_shape(),
            "Tape": union([rail.tape_shape(0, side) for side in (-1, 1)]),
        }
        pose = {"attachment_world_axes_x_mm": [0], "expected_carrier_yaw_deg": 0}
        result = supported_carrier_slide(shapes, obstacles, pose)
        self.assertTrue(result["passed"], result)
        mount = next(row for row in result["parts"] if row["part"] == "AccessoryMount")
        self.assertEqual(len(mount["regions"]), 8)
        self.assertLess(mount["shape_outside_service_envelope_mm3"], 1e-7)
        self.assertTrue(
            all(
                "face-prism" in segment["method"]
                for region in mount["regions"]
                for segment in region["segments"]
            )
        )
        shapes["AccessoryMount"] = carrier.fuse(
            Part.makeBox(1, 1, 1, App.Vector(20, 0, 16.4))
        )
        self.assertFalse(supported_carrier_slide(shapes, obstacles, pose)["passed"])

    def test_carrier_screw_sweep_rejects_uncovered_saved_protrusion(self):
        from gondola.parts import rail
        from gondola.validation.rail_access import supported_carrier_slide

        name = "BatteryEquipmentModuleRailMountScrew"
        screw = rail.attachment_screw_shape().fuse(
            Part.makeBox(1, 1, 1, App.Vector(1.4, 0, 6))
        )
        result = supported_carrier_slide(
            {name: screw},
            {},
            {"attachment_world_axes_x_mm": [0], "expected_carrier_yaw_deg": 0},
        )
        self.assertFalse(result["passed"])
        self.assertGreater(result["parts"][0]["actual_shape_outside_envelope_mm3"], 0.1)

    def test_saved_service_reports_every_populated_carriers_supported_trim(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256
        from gondola.validation.rail_access import rail_attachment_service

        before = file_sha256(BASELINE_FILE)
        doc = App.openDocument(str(BASELINE_FILE), hidden=True)
        try:
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
            report = rail_attachment_service(doc, registry, objects)
            self.assertTrue(report["passed"], report)
            carriers = [
                row for row in report["modules"] if not row["paired_propulsion_clamp"]
            ]
            self.assertEqual(len(carriers), 3)
            for carrier in carriers:
                trim = carrier["populated_supported_trim"]
                self.assertTrue(trim["passed"], trim)
                expected_travel = 6
                self.assertAlmostEqual(trim["travel_mm"], expected_travel)
                self.assertTrue(
                    any(row["part"].endswith("RailMountScrew") for row in trim["parts"])
                )
                self.assertTrue(
                    any(row["part"].endswith("RailMountNut") for row in trim["parts"])
                )
        finally:
            App.closeDocument(doc.Name)
            self.assertEqual(file_sha256(BASELINE_FILE), before)


if __name__ == "__main__":
    unittest.main()
