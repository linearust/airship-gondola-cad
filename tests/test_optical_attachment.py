"""The FC and optical head share one explicit native adjustment, without aliases."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalCommonPlatformTests(unittest.TestCase):
    def setUp(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        self.path = BASELINE_FILE
        self.sha = file_sha256(self.path)
        self.doc = App.openDocument(str(self.path), hidden=True)
        self.addCleanup(self.close_without_saving)

    def close_without_saving(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.sha)

    def test_only_shared_stage_moves_and_fc_to_sensor_transform_is_invariant(self):
        from gondola.parts import instrument_mount
        from gondola.validation.optical_envelopes import instrument_context

        doc = self.doc
        expected = (
            doc.ModuleFCEnvelope.getGlobalPlacement()
            .inverse()
            .multiply(doc.OpticalSensorFrame.getGlobalPlacement())
        )
        module_pose = doc.ElectronicsEquipmentModule.Placement.copy()
        for requested in (-999, -13, 0, 11, 999):
            instrument_mount.set_pitch(doc, requested)
            angle = max(-20, min(20, requested))
            rotation = App.Rotation(App.Vector(0, 1, 0), angle)
            literal = App.Placement(
                App.Vector(0, 0, 27.5) - rotation.multVec(App.Vector(0, 0, 8)), rotation
            )
            self.assertTrue(doc.InstrumentPitchStage.Placement.isSame(literal, 1e-7))
            actual = (
                doc.ModuleFCEnvelope.getGlobalPlacement()
                .inverse()
                .multiply(doc.OpticalSensorFrame.getGlobalPlacement())
            )
            self.assertTrue(actual.isSame(expected, 1e-7))
            self.assertTrue(
                doc.ElectronicsEquipmentModule.Placement.isSame(module_pose, 1e-7)
            )
            instrument_context(doc.OpticalFlowModule)
        for name in (
            "OpticalPitchStage",
            "OpticalRollStage",
            "OpticalMountBase",
            "OpticalPitchBolt",
            "OpticalFlowModuleRailMountScrew",
            "OpticalSensorTray",
            "OpticalFootBolt1",
            "OpticalFootNut1",
        ):
            self.assertIsNone(doc.getObject(name))
        self.assertEqual(
            doc.OpticalFlowModule.getParentGeoFeatureGroup(), doc.InstrumentPitchStage
        )
        self.assertEqual(
            doc.ElectronicsMount.getParentGeoFeatureGroup(), doc.InstrumentPitchStage
        )
        self.assertTrue(doc.OpticalFlowModule.Placement.isSame(App.Placement(), 1e-7))

    def test_old_modes_and_independent_sensor_control_fail_closed(self):
        from gondola.validation.optical import _source_evidence
        from gondola.validation.optical_envelopes import motion_bounds

        group = self.doc.OpticalFlowModule
        for mode in ("carrier", "rail", "legacy"):
            group.OpticalAttachmentMode = mode
            self.assertFalse(_source_evidence(self.doc)["passed"])
            with self.assertRaises(ValueError):
                motion_bounds(group)
        group.OpticalAttachmentMode = "instrument"
        self.doc.OpticalSensorFrame.addProperty("App::PropertyAngle", "Pitch")
        with self.assertRaises(ValueError):
            motion_bounds(group)

    def test_missing_wrong_parent_or_compensated_native_stage_is_rejected(self):
        from gondola.validation.optical_envelopes import motion_bounds

        frame, sensor = self.doc.OpticalSensorFrame, self.doc.ModuleMTF02PEnvelope
        frame.removeObject(sensor)
        self.doc.OpticalFlowModule.addObject(sensor)
        with self.assertRaises(ValueError):
            motion_bounds(self.doc.OpticalFlowModule)
        self.doc.OpticalFlowModule.removeObject(sensor)
        frame.addObject(sensor)
        frame.Placement.Base.x = 1
        sensor.Placement.Base.x = -1
        with self.assertRaises(ValueError):
            motion_bounds(self.doc.OpticalFlowModule)
        frame.Placement = App.Placement()
        sensor.Placement = App.Placement()
        stage = self.doc.InstrumentPitchStage
        stage.setExpression("Placement.Base.z", None)
        with self.assertRaises(ValueError):
            motion_bounds(self.doc.OpticalFlowModule)

    def test_continuous_body_bounds_contain_full_saved_sensor_over_common_pitch(
        self,
    ):
        from gondola.cad import placed_shape
        from gondola.parts import instrument_mount
        from gondola.validation.geometry import local_shape
        from gondola.validation.optical_envelopes import motion_bounds

        module = self.doc.ElectronicsEquipmentModule
        module.setExpression("Placement.Base.x", None)
        module.Placement = App.Placement(
            App.Vector(31, -17, 8), App.Rotation(App.Vector(1, 2, 3), 29)
        )
        self.doc.recompute()
        bound = motion_bounds(self.doc.OpticalFlowModule)["MTF02PContinuousBodyBound"]
        saved = local_shape(self.doc.ModuleMTF02PEnvelope)
        for angle in (-20, 0, 20):
            instrument_mount.set_pitch(self.doc, angle)
            shape = saved.copy()
            shape = placed_shape(
                shape, self.doc.OpticalSensorFrame.getGlobalPlacement()
            )
            with self.subTest(angle=angle):
                self.assertLess(abs(shape.cut(bound).Volume), 1e-5)

    def test_unknown_carrier_and_sensor_stock_cannot_be_ignored_by_power_envelopes(
        self,
    ):
        from gondola.validation.optical_envelopes import motion_bounds

        carrier = self.doc.ElectronicsMount
        original = carrier.Shape.copy()
        carrier.Shape = carrier.Shape.fuse(
            Part.makeBox(1.5, 1, 1, App.Vector(32.5, 2, 18.5))
        ).removeSplitter()
        with self.assertRaisesRegex(ValueError, "stock"):
            motion_bounds(self.doc.OpticalFlowModule)
        carrier.Shape = original
        sensor = self.doc.ModuleMTF02PEnvelope
        sensor.Shape = sensor.Shape.fuse(
            Part.makeBox(2, 2, 2, App.Vector(-1, -1, 65))
        ).removeSplitter()
        with self.assertRaisesRegex(ValueError, "sensor geometry"):
            motion_bounds(self.doc.OpticalFlowModule)

    def test_equipment_screens_move_fc_and_preserve_unknown_stage_members(self):
        from gondola.cad import world_shape
        from gondola.parts import instrument_mount
        from gondola.validation.equipment_options import _optical_screens

        extra = self.doc.addObject("Part::Feature", "UnknownInstrumentStock")
        extra.Shape = Part.makeBox(1, 1, 1, App.Vector(31, 31, 21))
        self.doc.InstrumentPitchStage.addObject(extra)
        self.doc.DesignRegistry.PrintedParts = list(
            self.doc.DesignRegistry.PrintedParts
        ) + [extra]
        screens = _optical_screens(self.doc)
        self.assertEqual(len(screens), 2)
        for screen in screens:
            self.assertIn(extra.Name, screen["saved_moving_parts"])
            self.assertIn("ModuleFCEnvelope", screen["saved_moving_parts"])
            for pose in screen["poses"]:
                instrument_mount.set_pitch(self.doc, pose["instrument_pitch_deg"])
                for name in ("ModuleFCEnvelope", extra.Name):
                    actual = world_shape(self.doc.getObject(name))
                    self.assertLess(
                        abs(actual.cut(pose["physical"][name]).Volume), 1e-5
                    )
                    self.assertLess(
                        abs(pose["physical"][name].cut(actual).Volume), 1e-5
                    )
                self.assertIn("FCWiringClearanceReserve", pose["instrument_reserves"])

    def test_continuous_registered_external_field_contains_both_profiles(self):
        from gondola.cad import placed_shape
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import instrument_mount, optical_sensor
        from gondola.validation.optical_envelopes import external_field_bound

        module = self.doc.ElectronicsEquipmentModule
        module.setExpression("Placement.Base.x", None)
        module.Placement = App.Placement(
            App.Vector(-23, 19, 11), App.Rotation(App.Vector(2, -1, 3), 37)
        )
        self.doc.recompute()
        for profile in SENSOR_PROFILES.values():
            bound, metadata = external_field_bound(self.doc.OpticalFlowModule, profile)
            self.assertEqual(metadata["instrument_pitch_range_deg"], (-20, 20))
            for angle in (-20, -7, 0, 13, 20):
                instrument_mount.set_pitch(self.doc, angle)
                field = optical_sensor.optical_reserve_shape(profile)
                field = placed_shape(
                    field, self.doc.OpticalSensorFrame.getGlobalPlacement()
                )
                # The field is a convex rectangular frustum and the cone is
                # convex; containing all vertices contains its entire volume.
                for vertex in field.Vertexes:
                    self.assertTrue(
                        bound.isInside(vertex.Point, 1e-5, True),
                        (profile.key, angle, tuple(vertex.Point)),
                    )
