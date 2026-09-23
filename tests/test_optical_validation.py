"""Negative native-CAD regressions for the pinned adjustable optical stack."""

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
            "The pinned reference must include the reviewed adjustable optical stack.",
        )

    def close_without_changing_baseline(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.original_sha)

    def test_changed_sensor_purchase_or_qualification_metadata_is_rejected(self):
        from gondola.validation.optical import _source_evidence

        self.assertTrue(_source_evidence(self.doc)["passed"])
        sensor = self.doc.ModuleMTF02PEnvelope
        screw = self.doc.OpticalRollBolt
        pivot = self.doc.OpticalRollBolt
        mutations = (
            (sensor, "ListedMassGrams", 99.0),
            (sensor, "OpticalDirection", App.Vector(1, 0, 0)),
            (sensor, "PlannedConnectorDirection", App.Vector(-1, 0, 0)),
            (sensor, "PublishedOpticalFlowFOV", 43.0),
            (sensor, "InstalledConnectorFitVerified", True),
            (self.doc.OpticalFlowModule, "SelfLevelling", True),
            (screw, "MaterialSelection", "A2 stainless steel"),
            (screw, "SourceURL", "https://example.invalid/unverified-screw"),
            (pivot, "HardwareSKU", "M2X6_BUTTON_HEAD"),
            (self.doc.OpticalRollNut, "HardwareSKU", "M2_UNQUALIFIED_NUT"),
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

    def test_changed_latch_coupon_geometry_or_orientation_is_rejected(self):
        from gondola.validation.optical import _source_evidence

        coupon = self.doc.OpticalLatchHostCoupon
        shape, rotation = coupon.Shape.copy(), coupon.PrintRotation
        try:
            coupon.PrintRotation = App.Rotation()
            self.assertFalse(_source_evidence(self.doc)["passed"])
            coupon.PrintRotation = rotation
            coupon.Shape = coupon.Shape.fuse(
                Part.makeBox(1, 1, 1, App.Vector(-10, 0, 2))
            )
            self.assertFalse(_source_evidence(self.doc)["passed"])
        finally:
            coupon.Shape, coupon.PrintRotation = shape, rotation
        self.assertTrue(_source_evidence(self.doc)["passed"])

    def test_obsolete_optical_washer_cannot_remain_in_the_purchase_registry(self):
        from gondola.validation.optical import _source_evidence

        old = list(self.doc.DesignRegistry.HardwareParts)
        obsolete = self.doc.addObject("Part::Feature", "ObsoleteOpticalWasher")
        obsolete.Shape = Part.makeCylinder(2.5, 0.3)
        self.doc.OpticalFlowModule.addObject(obsolete)
        try:
            self.doc.DesignRegistry.HardwareParts = old + [obsolete]
            result = _source_evidence(self.doc)
            self.assertFalse(result["passed"])
            self.assertFalse(
                result["registered_kit_inventory_matches_factory"]["HardwareParts"]
            )
        finally:
            self.doc.DesignRegistry.HardwareParts = old
            self.doc.removeObject(obsolete.Name)

    def test_early_failure_restores_fc_host_angles_and_saved_file(self):
        from gondola.parts import optical_mount, stack_interface
        from gondola.provenance import file_sha256
        from gondola.validation.optical import mtf_sensor_check

        group = self.doc.OpticalFlowModule
        host = self.doc.ElectronicsEquipmentModule
        stack_interface.attach_to_host(group, host)
        optical_mount.set_angles(self.doc, 13, -9)
        placement = group.Placement.copy()
        metadata = {
            name: getattr(group, name)
            for name in ("StackHostName", "StackInterfaceContract", "StackFitVerified")
        }
        original = self.doc.MTF02POpticalClearanceReserve.InstalledOpticalFieldVerified
        try:
            self.doc.MTF02POpticalClearanceReserve.InstalledOpticalFieldVerified = True
            result = mtf_sensor_check(self.doc)
            self.assertFalse(result["passed"])
            self.assertFalse(result["source_evidence"]["passed"])
            self.assertIs(group.getParentGeoFeatureGroup(), host)
            self.assertLess((group.Placement.Base - placement.Base).Length, 1e-9)
            self.assertTrue(group.Placement.Rotation.isSame(placement.Rotation, 1e-9))
            self.assertEqual(self.doc.OpticalRollStage.Roll.Value, 13)
            self.assertEqual(self.doc.OpticalPitchStage.Pitch.Value, -9)
            for name, value in metadata.items():
                self.assertEqual(getattr(group, name), value)
            self.assertEqual(file_sha256(self.path), self.original_sha)
        finally:
            self.doc.MTF02POpticalClearanceReserve.InstalledOpticalFieldVerified = (
                original
            )

    def test_invalid_host_fails_without_reparenting_or_changing_controls(self):
        from gondola.parts import optical_mount, stack_interface
        from gondola.validation.optical import mtf_sensor_check

        group = self.doc.OpticalFlowModule
        host = group.getParentGeoFeatureGroup()
        unsupported = self.doc.addObject("App::Part", "UnsupportedOpticalHost")
        optical_mount.set_angles(self.doc, 13, -9)
        placement = group.Placement.copy()
        for changed_parent in (None, unsupported):
            with self.subTest(parent=changed_parent):
                host.removeObject(group)
                if changed_parent is not None:
                    changed_parent.addObject(group)
                try:
                    result = mtf_sensor_check(self.doc)
                    self.assertFalse(result["passed"])
                    self.assertFalse(
                        result["source_evidence"]["native_structure"]["passed"]
                    )
                    self.assertIs(group.getParentGeoFeatureGroup(), changed_parent)
                    self.assertLess(
                        (group.Placement.Base - placement.Base).Length, 1e-9
                    )
                    self.assertTrue(
                        group.Placement.Rotation.isSame(placement.Rotation, 1e-9)
                    )
                    self.assertEqual(self.doc.OpticalRollStage.Roll.Value, 13)
                    self.assertEqual(self.doc.OpticalPitchStage.Pitch.Value, -9)
                finally:
                    stack_interface.attach_to_host(group, host)

    def test_missing_host_support_or_native_metadata_returns_a_failed_report(self):
        from gondola.validation.optical import mtf_sensor_check

        self.doc.removeObject("BatteryMount")
        self.doc.OpticalFlowModule.removeProperty("StackInterfaceContract")
        result = mtf_sensor_check(self.doc)
        self.assertFalse(result["passed"])
        errors = result["source_evidence"]["native_structure"]["errors"]
        self.assertIn({"object": "BatteryMount", "error": "missing object"}, errors)
        self.assertIn(
            {
                "object": "OpticalFlowModule",
                "missing_properties": ["StackInterfaceContract"],
            },
            errors,
        )

    def test_tilted_reservations_detect_wire_conflicts_without_body_collisions(self):
        from gondola.cad import belongs_to_group, world_shape
        from gondola.parts import optical_mount, optical_sensor, stack_interface
        from gondola.validation import optical

        group = self.doc.OpticalFlowModule
        host = self.doc.ElectronicsEquipmentModule
        stack_interface.attach_to_host(group, host)
        registry = self.doc.DesignRegistry
        physical = (
            list(registry.PrintedParts)
            + list(registry.HardwareParts)
            + list(registry.ReferenceParts)
            + list(registry.TapeReferences)
        )
        kit = [obj for obj in physical if belongs_to_group(obj, group)]
        reserve = self.doc.CapacitorServiceReserve
        inverse = reserve.getParentGeoFeatureGroup().getGlobalPlacement().inverse()
        sensor_midpoint = optical_sensor.SENSOR_BOTTOM_Z + optical_sensor.SIZE_MM[2] / 2
        for kind, local_point in (
            ("connector_intersection", App.Vector(20, 0, sensor_midpoint)),
            ("connector_gap", App.Vector(23.55, 0, sensor_midpoint)),
            ("optical_field", App.Vector(0, 0, sensor_midpoint + 80)),
        ):
            with self.subTest(kind=kind):
                optical_mount.set_angles(self.doc, 20, 20)
                point = self.doc.OpticalPitchStage.getGlobalPlacement().multVec(
                    local_point
                )
                blocker = Part.makeSphere(0.25, point)
                self.assertTrue(
                    all(
                        world_shape(obj).common(blocker).Volume < 1e-6
                        for obj in physical
                    )
                )
                if kind.startswith("connector"):
                    lane = world_shape(self.doc.MTF02PConnectorReserve)
                    if kind == "connector_intersection":
                        self.assertGreater(lane.common(blocker).Volume, 0.06)
                    else:
                        self.assertLess(lane.common(blocker).Volume, 1e-6)
                        self.assertAlmostEqual(
                            lane.distToShape(blocker)[0], 0.5, places=6
                        )
                    optical_mount.set_angles(self.doc, 0, 0)
                    self.assertLess(
                        world_shape(self.doc.MTF02PConnectorReserve)
                        .common(blocker)
                        .Volume,
                        1e-6,
                    )
                reserve.Shape = Part.makeSphere(0.25, inverse.multVec(point))
                reserve.Placement = App.Placement()
                with patch.object(optical, "ANGLES", (20,)):
                    result = optical._host_checks(self.doc, host, physical, kit)
                row = result["sampled_attitudes"][0]
                if kind == "optical_field":
                    self.assertIn(
                        reserve.Name,
                        [
                            hit["object"]
                            for hit in row["optical_reserved_space_intrusions"]
                        ],
                    )
                    self.assertIn(
                        reserve.Name,
                        [
                            hit["object"]
                            for hit in result["continuous_external_optical_bound"][
                                "external_reserved_space_intrusions"
                            ]
                        ],
                    )
                else:
                    failure = next(
                        check
                        for check in row["connector_reserved_space_clearances"]
                        if check["object"] == reserve.Name
                    )
                    self.assertFalse(failure["passed"])
                    if kind == "connector_intersection":
                        self.assertGreater(failure["intersection_mm3"], 0.06)
                    else:
                        self.assertAlmostEqual(
                            failure["measured_gap_mm"], 0.5, places=6
                        )
                self.assertFalse(result["passed"])

    def test_late_failure_or_exception_restores_host_angles_and_metadata(self):
        from gondola.parts import optical_mount, stack_interface
        from gondola.validation import optical

        group = self.doc.OpticalFlowModule
        host = self.doc.ElectronicsEquipmentModule
        stack_interface.attach_to_host(group, host)
        optical_mount.set_angles(self.doc, 13, -9)
        placement = group.Placement.copy()
        metadata = {
            name: getattr(group, name)
            for name in ("StackHostName", "StackInterfaceContract", "StackFitVerified")
        }
        for raises in (False, True):
            with self.subTest(raises=raises):

                def late_failure(doc, probe_host, physical, kit):
                    stack_interface.attach_to_host(group, probe_host)
                    optical_mount.set_angles(doc, -20, 20)
                    if raises:
                        raise RuntimeError("injected late clearance failure")
                    return {"passed": False}

                with (
                    patch.object(
                        optical, "_source_evidence", return_value={"passed": True}
                    ),
                    patch.object(optical, "_host_checks", side_effect=late_failure),
                ):
                    if raises:
                        with self.assertRaisesRegex(RuntimeError, "injected late"):
                            optical.mtf_sensor_check(self.doc)
                    else:
                        self.assertFalse(optical.mtf_sensor_check(self.doc)["passed"])
                self.assertIs(group.getParentGeoFeatureGroup(), host)
                self.assertLess((group.Placement.Base - placement.Base).Length, 1e-9)
                self.assertTrue(
                    group.Placement.Rotation.isSame(placement.Rotation, 1e-9)
                )
                self.assertEqual(self.doc.OpticalRollStage.Roll.Value, 13)
                self.assertEqual(self.doc.OpticalPitchStage.Pitch.Value, -9)
                for name, value in metadata.items():
                    self.assertEqual(getattr(group, name), value)

    def test_continuous_field_bound_detects_a_small_external_obstruction(self):
        from gondola.validation.optical import _external_field_bound
        from gondola.validation.wiring import collision_hits

        group = self.doc.OpticalFlowModule
        bound, _ = _external_field_bound(group)
        obstruction = Part.makeBox(1, 1, 1, App.Vector(0, 0, 50))
        obstruction.Placement = group.getGlobalPlacement()
        result = collision_hits(
            bound, {"IntroducedOpticalObstruction": obstruction}, tolerance=1e-5
        )
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["intersection_mm3"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
