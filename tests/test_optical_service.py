"""Sensor-only extraction leaves the integral carrier and all obstacles installed."""

import tempfile
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalMountingServiceTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import belongs_to_group
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        self.path = BASELINE_FILE
        self.before = file_sha256(self.path)
        self.doc = App.openDocument(str(self.path), hidden=True)
        self.addCleanup(self.close_without_saving)
        r = self.doc.DesignRegistry
        self.physical = (
            list(r.PrintedParts)
            + list(r.HardwareParts)
            + list(r.ReferenceParts)
            + list(r.TapeReferences)
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

    def test_both_profiles_lift_without_removing_fc_or_integral_carrier(self):
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import instrument_mount, optical_sensor
        from gondola.validation.optical_service import mounting_service_check

        for profile in SENSOR_PROFILES.values():
            optical_sensor.apply_profile(self.doc, profile)
            for angle in (-20, 0, 20):
                instrument_mount.set_pitch(self.doc, angle)
                report = mounting_service_check(self.doc, self.physical, self.kit)
                self.assertTrue(report["passed"], (profile.key, angle, report))
                self.assertEqual(report["moving_parts"], ["ModuleMTF02PEnvelope"])
                self.assertEqual(
                    report["paths"][0]["segments"][0]["end_mm"], (0, 0, 40)
                )
                for name in (
                    "ModuleFCEnvelope",
                    "ElectronicsMount",
                    "InstrumentMountBase",
                ):
                    self.assertIn(name, report["retained_parts"])

    def test_current_integral_carrier_service_survives_save_and_reopen(self):
        from gondola.cad import belongs_to_group
        from gondola.validation.optical_service import mounting_service_check

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "optical.FCStd"
            self.doc.saveCopy(str(path))
            reopened = App.openDocument(str(path), hidden=True)
            try:
                r = reopened.DesignRegistry
                physical = (
                    list(r.PrintedParts)
                    + list(r.HardwareParts)
                    + list(r.ReferenceParts)
                    + list(r.TapeReferences)
                )
                kit = [
                    obj
                    for obj in physical
                    if belongs_to_group(obj, reopened.OpticalFlowModule)
                ]
                self.assertTrue(
                    mounting_service_check(reopened, physical, kit)["passed"]
                )
            finally:
                App.closeDocument(reopened.Name)

    def test_unknown_midpath_obstacle_is_not_removed_with_the_sensor(self):
        from gondola.cad import world_shape
        from gondola.validation.optical_service import mounting_service_check

        frame = self.doc.OpticalSensorFrame
        # Beyond the selected body, inside its continuous extraction path.
        point = frame.getGlobalPlacement().multVec(App.Vector(0, 0, 80))
        blocker = self.doc.addObject("Part::Feature", "SensorServiceBlocker")
        blocker.Shape = Part.makeSphere(0.2, point)
        self.assertTrue(
            all(
                world_shape(obj).common(blocker.Shape).Volume < 1e-5
                for obj in self.physical
            )
        )
        report = mounting_service_check(self.doc, self.physical + [blocker], self.kit)
        self.assertFalse(report["passed"])
        self.assertIn(
            blocker.Name,
            [hit["object"] for hit in report["paths"][0]["segments"][0]["collisions"]],
        )

    def test_missing_sensor_or_host_does_not_pass_vacuously(self):
        from gondola.validation.optical_service import mounting_service_check

        self.assertFalse(mounting_service_check(self.doc, self.physical, [])["passed"])
        physical = [obj for obj in self.physical if obj.Name != "ElectronicsMount"]
        self.assertFalse(mounting_service_check(self.doc, physical, self.kit)["passed"])

    def test_unknown_optical_descendant_is_not_inferred_to_be_removable(self):
        from gondola.validation.optical_service import mounting_service_check

        extra = self.doc.addObject("Part::Feature", "UnknownOpticalHardware")
        extra.Shape = Part.makeBox(1, 1, 1, App.Vector(0, 0, 70))
        self.doc.OpticalFlowModule.addObject(extra)
        report = mounting_service_check(
            self.doc, self.physical + [extra], self.kit + [extra]
        )
        self.assertFalse(report["passed"])
        self.assertEqual(report["unexpected_moving_parts"], [extra.Name])

    def test_changed_carrier_stock_is_rejected_before_service(self):
        from gondola.validation.optical_service import mounting_service_check

        part = self.doc.ElectronicsMount
        part.Shape = part.Shape.fuse(Part.makeBox(1, 1, 1, App.Vector(0, 0, 43.5)))
        result = mounting_service_check(self.doc, self.physical, self.kit)
        self.assertFalse(result["passed"])
        self.assertIn("stock", result["error"])
