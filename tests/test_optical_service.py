"""Continuous mounting service retains FC, common plate and unknown obstacles."""

import tempfile
import unittest
from pathlib import Path

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
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

    def test_both_profiles_have_two_fasteners_and_checked_outward_then_lift_service(
        self,
    ):
        from gondola.cad import world_shape
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import instrument_mount, optical_sensor
        from gondola.validation.optical_service import (
            mount_tool_check,
            mounting_service_check,
        )

        for profile in SENSOR_PROFILES.values():
            optical_sensor.apply_profile(self.doc, profile)
            for angle in (-20, 0, 20):
                instrument_mount.set_pitch(self.doc, angle)
                tools = mount_tool_check(
                    self.doc.OpticalFlowModule,
                    {obj.Name: world_shape(obj) for obj in self.physical},
                )
                self.assertTrue(tools["passed"], (profile.key, angle, tools))
            instrument_mount.set_pitch(self.doc, 0)
            report = mounting_service_check(self.doc, self.physical, self.kit)
            self.assertTrue(report["passed"], report)
            self.assertEqual(
                [row["part"] for row in report["paths"][:4]],
                [
                    "OpticalFootNut1",
                    "OpticalFootNut2",
                    "OpticalFootBolt1",
                    "OpticalFootBolt2",
                ],
            )
            bracket = next(
                row
                for row in report["paths"]
                if row["part"].endswith("/OpticalSensorTray")
            )
            self.assertEqual(
                [row["end_mm"] for row in bracket["segments"]],
                [(0, 10, 0), (0, 10, 40)],
            )
            self.assertIn("ModuleFCEnvelope", report["retained_parts"])
            self.assertIn("ElectronicsMount", report["retained_parts"])
            self.assertIn("InstrumentMountBase", report["retained_parts"])

    def test_straight_lift_crosses_retained_fc_and_is_not_the_approved_path(self):
        from gondola.cad import world_shape
        from gondola.validation.geometry import translation_sweep

        group = self.doc.OpticalFlowModule
        inverse = group.getGlobalPlacement().inverse()
        foot = Part.makeBox(54, 8, 2, App.Vector(-27, -4, 0))
        sweep, _ = translation_sweep(foot, (0, 0, 40))
        fc = world_shape(self.doc.ModuleFCEnvelope)
        fc.Placement = inverse.multiply(fc.Placement)
        self.assertGreater(sweep.common(fc).Volume, 40)

    def test_tool_midpath_unknown_blocker_is_retained(self):
        from gondola.cad import world_shape
        from gondola.validation.optical_service import mount_tool_check

        group = self.doc.OpticalFlowModule
        point = group.getGlobalPlacement().multVec(App.Vector(19, 0, -10))
        blocker = Part.makeSphere(0.15, point)
        obstacles = {obj.Name: world_shape(obj) for obj in self.physical}
        self.assertTrue(
            all(blocker.common(shape).Volume < 1e-5 for shape in obstacles.values())
        )
        report = mount_tool_check(group, {**obstacles, "UnknownToolBlocker": blocker})
        self.assertFalse(report["passed"])
        self.assertIn(
            "UnknownToolBlocker",
            [hit["object"] for row in report["tools"] for hit in row["collisions"]],
        )

    def test_current_rounded_bracket_service_survives_native_save_reopen(self):
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
                report = mounting_service_check(reopened, physical, kit)
                self.assertTrue(report["passed"], report)
                bracket = next(
                    row
                    for row in report["paths"]
                    if row["part"].endswith("/OpticalSensorTray")
                )
                self.assertLess(
                    bracket["conservative_enclosure"]["uncovered_saved_stock_mm3"], 1e-5
                )
            finally:
                App.closeDocument(reopened.Name)

    def test_added_stock_cannot_escape_the_literal_service_enclosures(self):
        from gondola.validation.optical_service import mounting_service_check

        tray = self.doc.OpticalSensorTray
        tray.Shape = tray.Shape.fuse(
            Part.makeBox(1.5, 1, 1, App.Vector(26.5, 2, 0.5))
        ).removeSplitter()
        self.assertTrue(tray.Shape.isValid())
        self.assertEqual(len(tray.Shape.Solids), 1)
        report = mounting_service_check(self.doc, self.physical, self.kit)
        self.assertFalse(report["passed"])
        row = next(
            row for row in report["paths"] if row["part"].endswith("/OpticalSensorTray")
        )
        self.assertGreater(
            row["conservative_enclosure"]["uncovered_saved_stock_mm3"], 0.99
        )

    def test_midpath_blockers_reject_nut_screw_and_bracket_routes(self):
        from gondola.cad import world_shape
        from gondola.validation.optical_service import mounting_service_check

        group = self.doc.OpticalFlowModule
        for part, point in (
            ("OpticalFootNut1", (-17.7, 0, 5.1)),
            ("OpticalFootBolt1", (-17.7, 0, -7)),
            ("CompleteOpticalBracket/OpticalSensorTray", (0, 7, 1)),
        ):
            with self.subTest(part=part):
                blocker = self.doc.addObject("Part::Feature", "ServiceMidpathBlocker")
                blocker.Shape = Part.makeSphere(0.1, App.Vector(*point))
                blocker.Placement = group.getGlobalPlacement()
                try:
                    obstacle = world_shape(blocker)
                    self.assertTrue(
                        all(
                            world_shape(obj).common(obstacle).Volume < 1e-5
                            for obj in self.physical
                        )
                    )
                    report = mounting_service_check(
                        self.doc, self.physical + [blocker], self.kit
                    )
                    self.assertFalse(report["passed"])
                    row = next(row for row in report["paths"] if row["part"] == part)
                    self.assertIn(
                        blocker.Name,
                        [
                            hit["object"]
                            for segment in row["segments"]
                            for hit in segment["collisions"]
                        ],
                    )
                finally:
                    self.doc.removeObject(blocker.Name)

    def test_missing_fastener_does_not_turn_removal_into_a_vacuous_pass(self):
        from gondola.validation.optical_service import mounting_service_check

        kit = [obj for obj in self.kit if obj.Name != "OpticalFootNut2"]
        result = mounting_service_check(self.doc, self.physical, kit)
        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_parts"], ["OpticalFootNut2"])
