"""Negative native-CAD regressions for the pinned selected optical pitch joint."""

import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalClearanceTests(unittest.TestCase):
    def setUp(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        self.path = BASELINE_FILE
        self.original_sha = file_sha256(self.path)
        self.doc = App.openDocument(str(self.path), hidden=True)
        self.addCleanup(self.close_without_changing_baseline)
        self.assertIsNotNone(
            self.doc.getObject("OpticalFlowModule"),
            "The pinned reference must include the reviewed optical joint.",
        )

    def close_without_changing_baseline(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.original_sha)

    def test_changed_sensor_purchase_or_qualification_metadata_is_rejected(self):
        from gondola.validation.optical import _source_evidence

        self.assertTrue(_source_evidence(self.doc)["passed"])
        sensor = self.doc.ModuleMTF02PEnvelope
        screw = self.doc.OpticalPitchBolt
        pivot = self.doc.OpticalPitchBolt
        mutations = (
            (sensor, "ListedMassGrams", 99.0),
            (sensor, "SensorModel", "MTF01P"),
            (sensor, "SensorProfileContract", "{}"),
            (self.doc.MTF02PConnectorReserve, "SensorModel", "MTF01P"),
            (self.doc.MTF02POpticalClearanceReserve, "SensorProfileContract", "{}"),
            (self.doc.OpticalFlowModule, "SensorModel", "MTF01P"),
            (self.doc.OpticalFlowModule, "SupportedSensorModels", ["MTF02P"]),
            (sensor, "OpticalDirection", App.Vector(1, 0, 0)),
            (sensor, "PlannedConnectorDirection", App.Vector(-1, 0, 0)),
            (sensor, "PublishedOpticalFlowFOV", 43.0),
            (sensor, "InstalledConnectorFitVerified", True),
            (self.doc.OpticalFlowModule, "SelfLevelling", True),
            (screw, "MaterialSelection", "A2 stainless steel"),
            (screw, "SourceURL", "https://example.invalid/unverified-screw"),
            (pivot, "HardwareSKU", "M2X6_BUTTON_HEAD"),
            (self.doc.OpticalPitchNut, "HardwareSKU", "M2_UNQUALIFIED_NUT"),
        )
        for obj, name, changed in mutations:
            with self.subTest(object=obj.Name, property=name):
                original = getattr(obj, name)
                try:
                    self.assertNotEqual(original, changed)
                    setattr(obj, name, changed)
                    self.assertFalse(_source_evidence(self.doc)["passed"])
                finally:
                    setattr(obj, name, original)
        self.assertTrue(_source_evidence(self.doc)["passed"])

    def test_changed_pitch_hardware_geometry_or_hierarchy_is_rejected(self):
        from gondola.validation.optical import _source_evidence

        bolt = self.doc.OpticalPitchBolt
        shape = bolt.Shape.copy()
        parent = bolt.getParentGeoFeatureGroup()
        try:
            bolt.Shape = bolt.Shape.fuse(
                Part.makeBox(1, 1, 1, bolt.Shape.BoundBox.Center)
            )
            self.assertFalse(_source_evidence(self.doc)["passed"])
            bolt.Shape = shape
            parent.removeObject(bolt)
            self.doc.BatteryEquipmentModule.addObject(bolt)
            self.assertFalse(_source_evidence(self.doc)["passed"])
        finally:
            bolt.Shape = shape
            self.doc.BatteryEquipmentModule.removeObject(bolt)
            parent.addObject(bolt)
        self.assertTrue(_source_evidence(self.doc)["passed"])

    def test_unexpected_optical_hardware_cannot_remain_in_registry(self):
        from gondola.validation.optical import _source_evidence

        original = list(self.doc.DesignRegistry.HardwareParts)
        obsolete = self.doc.addObject("Part::Feature", "OpticalRailClamp")
        obsolete.Shape = Part.makeCylinder(1, 8)
        self.doc.OpticalFlowModule.addObject(obsolete)
        try:
            self.doc.DesignRegistry.HardwareParts = original + [obsolete]
            self.assertFalse(_source_evidence(self.doc)["passed"])
        finally:
            self.doc.DesignRegistry.HardwareParts = original
            self.doc.removeObject(obsolete.Name)

    def test_wrong_parent_and_missing_controls_are_rejected_without_mutation(self):
        from gondola.validation.optical import mtf_sensor_check

        group = self.doc.OpticalFlowModule
        original = group.Placement.copy()
        host = group.getParentGeoFeatureGroup()
        if host is not None:
            host.removeObject(group)
        self.doc.ElectronicsEquipmentModule.addObject(group)
        try:
            result = mtf_sensor_check(self.doc)
            self.assertFalse(result["passed"])
            self.assertEqual(
                group.getParentGeoFeatureGroup(), self.doc.ElectronicsEquipmentModule
            )
            self.assertTrue(group.Placement.isSame(original, 1e-7))
        finally:
            self.doc.ElectronicsEquipmentModule.removeObject(group)
            if host is not None:
                host.addObject(group)
        group.removeProperty("OpticalMountContract")
        self.assertFalse(mtf_sensor_check(self.doc)["passed"])

    def test_missing_rail_registry_returns_failure_without_changing_cad(self):
        from gondola.parts.optical_mount import set_pitch
        from gondola.validation.optical import mtf_sensor_check

        # Use a non-neutral saved control to catch validation resetting the pose.
        set_pitch(self.doc, 11)
        self.doc.DesignRegistry.removeProperty("RailLocks")
        before_objects = tuple(obj.Name for obj in self.doc.Objects)
        before_properties = {
            obj.Name: tuple(obj.PropertiesList) for obj in self.doc.Objects
        }
        before_placements = {
            obj.Name: obj.Placement.copy()
            for obj in self.doc.Objects
            if "Placement" in obj.PropertiesList
        }
        before_sensor_model = self.doc.OpticalFlowModule.SensorModel
        before_sensor_shapes = {
            name: self.doc.getObject(name).Shape.exportBrepToString()
            for name in (
                "ModuleMTF02PEnvelope",
                "MTF02POpticalClearanceReserve",
                "MTF02PConnectorReserve",
            )
        }

        report = mtf_sensor_check(self.doc)

        self.assertFalse(report["passed"])
        structure = report["source_evidence"]["native_structure"]
        self.assertFalse(structure["passed"])
        self.assertIn(
            {"object": "DesignRegistry", "missing_properties": ["RailLocks"]},
            structure["errors"],
        )
        self.assertEqual(tuple(obj.Name for obj in self.doc.Objects), before_objects)
        for obj in self.doc.Objects:
            self.assertEqual(tuple(obj.PropertiesList), before_properties[obj.Name])
        for name, placement in before_placements.items():
            self.assertTrue(self.doc.getObject(name).Placement.isSame(placement, 1e-7))
        self.assertEqual(self.doc.OpticalPitchStage.Pitch.Value, 11)
        self.assertEqual(self.doc.OpticalFlowModule.SensorModel, before_sensor_model)
        for name, shape in before_sensor_shapes.items():
            self.assertEqual(self.doc.getObject(name).Shape.exportBrepToString(), shape)

    def test_both_sensors_visit_actual_attachment_and_restore_state_on_exception(self):
        from gondola.parts.optical_mount import set_pitch
        from gondola.validation import optical

        group = self.doc.OpticalFlowModule
        set_pitch(self.doc, 11)
        before = optical._saved_sensor_state(self.doc)
        selected = group.SensorModel
        mount = (str(group.OpticalAttachmentMode), tuple(group.Placement.Base))
        calls = []

        def screen(doc, physical, kit, *, profile):
            calls.append(
                (
                    profile.key,
                    (
                        str(doc.OpticalFlowModule.OpticalAttachmentMode),
                        tuple(doc.OpticalFlowModule.Placement.Base),
                    ),
                )
            )
            if len(calls) == 2:
                raise RuntimeError("deliberate validation failure")
            return {"passed": True}

        with (
            patch.object(optical, "_placement_checks", side_effect=screen),
            patch.object(
                optical, "_attachment_service_checks", return_value={"passed": True}
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "deliberate"):
                optical.mtf_sensor_check(self.doc)
        self.assertEqual(calls, [("MTF02P", mount), ("MTF01P", mount)])
        self.assertEqual(group.SensorModel, selected)
        self.assertEqual(
            (str(group.OpticalAttachmentMode), tuple(group.Placement.Base)), mount
        )
        self.assertEqual(self.doc.OpticalPitchStage.Pitch.Value, 11)
        after = optical._saved_sensor_state(self.doc)
        for name, values in before.items():
            for key, value in values.items():
                if key == "Shape":
                    self.assertLess(abs(value.cut(after[name][key]).Volume), 1e-7)
                    self.assertLess(abs(after[name][key].cut(value).Volume), 1e-7)
                elif key == "Placement":
                    self.assertTrue(value.isSame(after[name][key], 1e-7))
                else:
                    self.assertEqual(value, after[name][key], (name, key))

    def test_continuous_field_does_not_filter_unknown_obstacles(self):
        from gondola.validation.optical import _external_field_bound
        from gondola.validation.wiring import collision_hits

        group = self.doc.OpticalFlowModule
        bound, _ = _external_field_bound(group)
        block = Part.makeBox(1, 1, 1, App.Vector(0, 0, 50))
        block.Placement = group.getGlobalPlacement()
        hits = collision_hits(bound, {"UnknownBlock": block}, tolerance=1e-5)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0]["intersection_mm3"], 1)

    def test_mtf01p_long_edge_connector_detects_external_obstruction(self):
        from gondola.cad import belongs_to_group, world_shape
        from gondola.contracts.optical_sensors import get_sensor_profile
        from gondola.parts import optical_mount, optical_sensor
        from gondola.validation import optical

        profile = get_sensor_profile("MTF01P")
        optical_sensor.apply_profile(self.doc, profile)
        optical_mount.set_pitch(self.doc, 0)
        registry = self.doc.DesignRegistry
        physical = (
            list(registry.PrintedParts)
            + list(registry.HardwareParts)
            + list(registry.ReferenceParts)
            + list(registry.TapeReferences)
        )
        kit = [
            obj for obj in physical if belongs_to_group(obj, self.doc.OpticalFlowModule)
        ]
        point = self.doc.OpticalPitchStage.getGlobalPlacement().multVec(
            App.Vector(
                0, profile.size_mm[1] / 2 + 5, optical_sensor.SENSOR_BOTTOM_Z + 8
            )
        )
        obstacle = Part.makeSphere(0.25, point)
        self.assertGreater(
            world_shape(self.doc.MTF02PConnectorReserve).common(obstacle).Volume, 0.06
        )
        self.assertTrue(
            all(world_shape(obj).common(obstacle).Volume < 1e-7 for obj in physical)
        )
        reserve = self.doc.CapacitorServiceReserve
        reserve.Shape = Part.makeSphere(
            0.25,
            reserve.getParentGeoFeatureGroup()
            .getGlobalPlacement()
            .inverse()
            .multVec(point),
        )
        reserve.Placement = App.Placement()
        with patch.object(optical, "ANGLES", (0,)):
            result = optical._placement_checks(self.doc, physical, kit, profile=profile)
        self.assertFalse(result["passed"])
        clearance = next(
            row
            for row in result["sampled_attitudes"][0][
                "connector_reserved_space_clearances"
            ]
            if row["object"] == reserve.Name
        )
        self.assertFalse(clearance["passed"])
        self.assertGreater(clearance["intersection_mm3"], 0.06)

    def test_selected_attachment_connectors_clear_maximum_battery_over_native_pitch_range(
        self,
    ):
        from gondola.cad import world_shape
        from gondola.contracts.optical_sensors import SENSOR_PROFILES
        from gondola.parts import optical_interface, optical_mount, optical_sensor

        # Use the saved selected attachment, registration allowance and native
        # pitch control. A neutral default-MTF02P test missed the MTF01P long
        # connector dipping within 1.5 mm after the carrier deck was raised.
        battery = world_shape(self.doc.MaximumBatteryEnvelope)
        group = self.doc.OpticalFlowModule
        inverse = group.getGlobalPlacement().inverse()
        for profile in SENSOR_PROFILES.values():
            optical_sensor.apply_profile(self.doc, profile)
            for angle in range(-20, 21):
                optical_mount.set_pitch(self.doc, angle)
                self.assertTrue(
                    self.doc.OpticalPitchStage.Placement.Rotation.isSame(
                        App.Rotation(App.Vector(0, 1, 0), angle), 1e-7
                    )
                )
                connector = world_shape(self.doc.MTF02PConnectorReserve)
                local = connector.copy()
                local.Placement = inverse.multiply(local.Placement)
                bound = optical_interface.registration_bound(
                    local, str(group.OpticalAttachmentMode)
                )
                bound.Placement = group.getGlobalPlacement()
                for kind, envelope in (("nominal", connector), ("registration", bound)):
                    with self.subTest(sensor=profile.key, pitch=angle, envelope=kind):
                        self.assertLess(abs(envelope.common(battery).Volume), 1e-7)
                        self.assertGreaterEqual(
                            envelope.distToShape(battery)[0], 1.5 - 1e-5
                        )
