"""Negative native-CAD regressions for the pinned adjustable optical stack."""

import unittest

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
        screw = self.doc.OpticalStackUpperBolt0
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
            (pivot, "HardwareSKU", "M2X8_SOCKET_CAP"),
            (self.doc.OpticalRollNut, "HardwareSKU", "M2_HEX_NUT"),
        )
        for obj, name, changed in mutations:
            with self.subTest(object=obj.Name, property=name):
                original = getattr(obj, name)
                try:
                    setattr(obj, name, changed)
                    self.assertFalse(_source_evidence(self.doc)["passed"])
                finally:
                    setattr(obj, name, original)
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

    def test_continuous_field_bound_detects_a_small_external_obstruction(self):
        from gondola.validation.optical import _external_field_bound, _hits

        group = self.doc.OpticalFlowModule
        bound, _ = _external_field_bound(group)
        obstruction = Part.makeBox(1, 1, 1, App.Vector(0, 0, 50))
        obstruction.Placement = group.getGlobalPlacement()
        result = _hits(bound, {"IntroducedOpticalObstruction": obstruction})
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["intersection_mm3"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
