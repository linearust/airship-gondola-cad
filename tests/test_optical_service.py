"""Pitch-tool access and ordered optical service use actual saved geometry."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalPitchServiceTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import belongs_to_group
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        self.path = BASELINE_FILE
        self.before = file_sha256(self.path)
        self.doc = App.openDocument(str(self.path), hidden=True)
        self.addCleanup(self.close_without_saving)
        registry = self.doc.DesignRegistry
        self.physical = (
            list(registry.PrintedParts)
            + list(registry.HardwareParts)
            + list(registry.ReferenceParts)
            + list(registry.TapeReferences)
        )
        self.kit = [
            obj
            for obj in self.physical
            if belongs_to_group(obj, self.doc.OpticalFlowModule)
        ]

    def close_without_saving(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.before)

    def test_both_profiles_clear_sampled_tool_access_and_neutral_disassembly(self):
        from gondola.cad import world_shape
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_mount, optical_sensor
        from gondola.validation.optical_service import (
            pitch_disassembly_check,
            pitch_tool_check,
        )

        for profile in SENSOR_PROFILES.values():
            optical_sensor.apply_profile(self.doc, profile)
            for angle in (-20, -10, 0, 10, 20):
                optical_mount.set_pitch(self.doc, angle)
                result = pitch_tool_check(
                    self.doc.OpticalFlowModule,
                    {obj.Name: world_shape(obj) for obj in self.physical},
                )
                self.assertTrue(result["passed"], (profile.key, angle, result))
            optical_mount.set_pitch(self.doc, 0)
            result = pitch_disassembly_check(self.doc, self.kit)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["paths"][0]["part"], "OpticalPitchNut")
            self.assertAlmostEqual(result["paths"][0]["translation_mm"][1], 4.7)
            self.assertEqual(result["paths"][1]["part"], "OpticalPitchBolt")
            self.assertAlmostEqual(result["paths"][1]["translation_mm"][1], -8.2)
        optical_mount.set_pitch(self.doc, 10)
        self.assertFalse(pitch_disassembly_check(self.doc, self.kit)["passed"])

    def test_tool_midpath_blocker_is_clear_of_installed_optical_parts(self):
        from gondola.cad import world_shape
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.optical_service import pitch_tool_check

        group = self.doc.OpticalFlowModule
        blocker = Part.makeSphere(0.25, App.Vector(0, -11.5, 19))
        blocker.Placement = group.getGlobalPlacement()
        obstacles = {obj.Name: world_shape(obj) for obj in self.physical}
        self.assertTrue(
            all(
                intersection_volume(blocker, shape) < 1e-5
                for shape in obstacles.values()
            )
        )
        result = pitch_tool_check(group, {**obstacles, "ToolMidpathBlocker": blocker})
        self.assertFalse(result["passed"])
        self.assertEqual(
            [row["object"] for row in result["collisions"]], ["ToolMidpathBlocker"]
        )

    def test_current_rounded_tray_clears_before_and_after_native_save_reopen(self):
        from gondola.cad import belongs_to_group
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_mount, optical_sensor
        from gondola.validation.optical_service import pitch_disassembly_check

        # Exercise today's builders even before a new regression fixture is
        # promoted. The prior fixture alone cannot detect a new curved face.
        self.doc.OpticalSensorTray.Shape = optical_mount.sensor_tray_shape()
        self.doc.OpticalMountBase.Shape = optical_mount.base_shape()
        optical_mount.set_pitch(self.doc, 0)

        def verify(doc, kit):
            result = pitch_disassembly_check(doc, kit)
            self.assertTrue(result["passed"], result)
            path = next(
                row
                for row in result["paths"]
                if row["part"] == "TrayAssembly/OpticalSensorTray"
            )
            self.assertLess(
                path["conservative_enclosure"]["uncovered_saved_stock_mm3"], 1e-5
            )
            self.assertEqual(
                path["method"], "continuous planar/coaxial-cylinder face-prism union"
            )

        with tempfile.TemporaryDirectory() as temporary:
            for profile in SENSOR_PROFILES.values():
                with self.subTest(profile=profile.key):
                    optical_sensor.apply_profile(self.doc, profile)
                    verify(self.doc, self.kit)
                    path = Path(temporary) / (profile.key + ".FCStd")
                    self.doc.saveCopy(str(path))
                    reopened = App.openDocument(str(path), hidden=True)
                    try:
                        registry = reopened.DesignRegistry
                        physical = (
                            list(registry.PrintedParts)
                            + list(registry.HardwareParts)
                            + list(registry.ReferenceParts)
                            + list(registry.TapeReferences)
                        )
                        kit = [
                            obj
                            for obj in physical
                            if belongs_to_group(obj, reopened.OpticalFlowModule)
                        ]
                        verify(reopened, kit)
                    finally:
                        App.closeDocument(reopened.Name)

    def test_tray_enclosure_rejects_added_stock_outside_its_literal_boundary(self):
        from gondola.validation.optical_service import pitch_disassembly_check

        tray = self.doc.OpticalSensorTray
        tray.Shape = tray.Shape.fuse(
            Part.makeBox(1.1, 1, 1, App.Vector(8.9, 0, 5.5))
        ).removeSplitter()
        self.assertTrue(tray.Shape.isValid())
        self.assertEqual(len(tray.Shape.Solids), 1)
        self.doc.recompute()
        result = pitch_disassembly_check(self.doc, self.kit)
        path = next(
            row
            for row in result["paths"]
            if row["part"] == "TrayAssembly/OpticalSensorTray"
        )
        self.assertFalse(result["passed"])
        self.assertFalse(path["passed"])
        self.assertGreater(
            path["conservative_enclosure"]["uncovered_saved_stock_mm3"], 0.99
        )

    def test_midpath_blocks_reject_each_disassembly_step_with_clear_endpoints(self):
        from gondola.cad import world_shape
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.optical_service import pitch_disassembly_check

        base = self.doc.OpticalMountBase
        original = base.Shape.copy()
        inverse = self.doc.OpticalFlowModule.getGlobalPlacement().inverse()
        nominal = pitch_disassembly_check(self.doc, self.kit)
        for name, point in (
            ("OpticalPitchNut", (2.0, 4.3, 19.0)),
            ("OpticalPitchBolt", (1.6, -8.0, 19.0)),
            ("TrayAssembly/OpticalSensorTray", (4.0, 8.0, 24.5)),
        ):
            with self.subTest(part=name):
                blocker = Part.makeSphere(0.2, App.Vector(*point))
                moving = world_shape(self.doc.getObject(name.split("/")[-1]))
                moving.Placement = inverse.multiply(moving.Placement)
                row = next(row for row in nominal["paths"] if row["part"] == name)
                self.assertLess(intersection_volume(moving, blocker), 1e-5)
                moving.translate(App.Vector(*row["translation_mm"]))
                self.assertLess(intersection_volume(moving, blocker), 1e-5)
                base.Shape = original.fuse(blocker)
                result = pitch_disassembly_check(self.doc, self.kit)
                self.assertFalse(result["passed"])
                path = next(row for row in result["paths"] if row["part"] == name)
                self.assertFalse(path["passed"], result)
                self.assertIn(
                    "OpticalMountBase", [hit["object"] for hit in path["collisions"]]
                )
                base.Shape = original

    def test_selected_tool_registration_rejects_offset_only_external_blocker(self):
        from gondola.cad import world_shape
        from gondola.validation import optical
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.optical_service import (
            pitch_tool_check,
            pitch_tool_shape,
        )

        group = self.doc.OpticalFlowModule
        blocker = self.doc.addObject("Part::Feature", "ToolRegistrationBlocker")
        blocker.Shape = Part.makeSphere(0.04, App.Vector(0.94, -11.5, 19))
        blocker.Placement = group.getGlobalPlacement()
        target = world_shape(blocker)
        obstacles = {obj.Name: world_shape(obj) for obj in self.physical + [blocker]}
        self.assertTrue(pitch_tool_check(group, obstacles)["passed"])
        shifted = pitch_tool_shape()
        shifted.Placement = group.getGlobalPlacement()
        shifted.translate(
            group.getGlobalPlacement().Rotation.multVec(App.Vector(0.1, 0, 0))
        )
        self.assertGreater(intersection_volume(shifted, target), 1e-5)
        with patch.object(optical, "ANGLES", (0,)):
            result = optical._placement_checks(
                self.doc, self.physical + [blocker], self.kit
            )
        self.assertFalse(result["passed"])
        pose = result["sampled_attitudes"][0]
        self.assertTrue(pose["pitch_clamp_tool_access"]["passed"])
        registered = next(
            row
            for row in pose["assembly_registration_checks"]
            if row["component"] == "pitch_tool"
        )
        self.assertFalse(registered["passed"])
        self.assertIn(
            blocker.Name,
            [row["object"] for row in registered["external_obstructions"]],
        )

    def test_equipment_and_power_screens_preserve_the_shared_tool_reserve(self):
        from gondola.power_export import _collisions, _optical_motion_bounds
        from gondola.validation.equipment_options import (
            _optical_option_check,
            _optical_screens,
        )

        blocker = Part.makeSphere(0.25, App.Vector(0, -11.5, 19))
        blocker.Placement = self.doc.OpticalFlowModule.getGlobalPlacement()
        report = _optical_option_check(
            _optical_screens(self.doc), {"ToolBlocker": blocker}
        )
        self.assertFalse(report["passed"])
        for sensor in report["sensor_screens"]:
            for pose in sensor["sampled_attitudes"]:
                self.assertEqual(
                    {hit["moving"] for hit in pose["collisions"]},
                    {"OpticalPitchToolAccess"},
                )
        bounds = _optical_motion_bounds(self.doc.OpticalFlowModule)
        hits = _collisions({"ToolBlocker": blocker}, bounds)
        self.assertEqual(
            {hit["second"] for hit in hits}, {"OpticalPitchToolAccessBound"}
        )


if __name__ == "__main__":
    unittest.main()
