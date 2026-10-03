"""Saved-native regressions for the rigid optical head and common FC stage."""

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

    def close_without_changing_baseline(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.original_sha)

    def test_changed_sensor_and_integral_support_metadata_is_rejected(self):
        from gondola.validation.optical import _source_evidence

        self.assertTrue(_source_evidence(self.doc)["passed"])
        mutations = (
            (self.doc.ModuleMTF02PEnvelope, "ListedMassGrams", 99.0),
            (self.doc.ModuleMTF02PEnvelope, "SensorModel", "MTF01P"),
            (self.doc.ModuleMTF02PEnvelope, "SensorProfileContract", "{}"),
            (self.doc.ModuleMTF02PEnvelope, "OpticalDirection", App.Vector(1, 0, 0)),
            (self.doc.ModuleMTF02PEnvelope, "InstalledConnectorFitVerified", True),
            (self.doc.MTF02PConnectorReserve, "SensorModel", "MTF01P"),
            (self.doc.MTF02POpticalClearanceReserve, "SensorProfileContract", "{}"),
            (self.doc.OpticalFlowModule, "SupportedSensorModels", ["MTF02P"]),
            (self.doc.OpticalFlowModule, "SelfLevelling", True),
            (self.doc.ElectronicsMount, "PrintSKU", "WrongCarrier"),
        )
        for obj, name, changed in mutations:
            original = getattr(obj, name)
            with self.subTest(object=obj.Name, property=name):
                try:
                    setattr(obj, name, changed)
                    self.assertFalse(_source_evidence(self.doc)["passed"])
                finally:
                    setattr(obj, name, original)

    def test_changed_integral_carrier_geometry_and_parent_are_rejected(self):
        from gondola.validation.optical import _source_evidence

        bolt = self.doc.ElectronicsMount
        shape, parent = bolt.Shape.copy(), bolt.getParentGeoFeatureGroup()
        try:
            bolt.Shape = bolt.Shape.fuse(Part.makeBox(1, 1, 1, App.Vector(0, 0, 43.5)))
            self.assertFalse(_source_evidence(self.doc)["passed"])
            bolt.Shape = shape
            parent.removeObject(bolt)
            self.doc.OpticalFlowModule.addObject(bolt)
            self.assertFalse(_source_evidence(self.doc)["passed"])
        finally:
            bolt.Shape = shape
            self.doc.OpticalFlowModule.removeObject(bolt)
            parent.addObject(bolt)

    def test_extra_optical_hardware_and_missing_sensor_fail_inventory(self):
        from gondola.validation.optical import _source_evidence

        registry = self.doc.DesignRegistry
        original = list(registry.HardwareParts)
        references = list(registry.ReferenceParts)
        extra = self.doc.addObject("Part::Feature", "UnreviewedOpticalClamp")
        extra.Shape = Part.makeCylinder(1, 5)
        self.doc.OpticalFlowModule.addObject(extra)
        try:
            self.assertFalse(_source_evidence(self.doc)["passed"])
            registry.HardwareParts = original + [extra]
            self.assertFalse(_source_evidence(self.doc)["passed"])
            registry.HardwareParts = original
            self.doc.removeObject(extra.Name)
            registry.ReferenceParts = [
                obj for obj in references if obj != self.doc.ModuleMTF02PEnvelope
            ]
            self.assertFalse(_source_evidence(self.doc)["passed"])
        finally:
            registry.HardwareParts = original
            registry.ReferenceParts = references

    def test_wrong_native_parent_is_rejected_before_any_mutation(self):
        from gondola.validation.optical import mtf_sensor_check

        group = self.doc.OpticalFlowModule
        original = group.Placement.copy()
        self.doc.InstrumentPitchStage.removeObject(group)
        self.doc.ElectronicsEquipmentModule.addObject(group)
        report = mtf_sensor_check(self.doc)
        self.assertFalse(report["passed"])
        self.assertEqual(
            group.getParentGeoFeatureGroup(), self.doc.ElectronicsEquipmentModule
        )
        self.assertTrue(group.Placement.isSame(original, 1e-7))

    def test_missing_registry_fails_without_resetting_saved_pitch_or_sensor(self):
        from gondola.parts.instrument_mount import set_pitch
        from gondola.validation.optical import mtf_sensor_check

        set_pitch(self.doc, 11)
        self.doc.DesignRegistry.removeProperty("RailLocks")
        objects = tuple(obj.Name for obj in self.doc.Objects)
        poses = {
            obj.Name: obj.Placement.copy()
            for obj in self.doc.Objects
            if "Placement" in obj.PropertiesList
        }
        shape = self.doc.ModuleMTF02PEnvelope.Shape.exportBrepToString()
        report = mtf_sensor_check(self.doc)
        self.assertFalse(report["passed"])
        self.assertEqual(tuple(obj.Name for obj in self.doc.Objects), objects)
        self.assertEqual(float(self.doc.InstrumentPitchStage.Pitch), 11)
        self.assertEqual(
            self.doc.ModuleMTF02PEnvelope.Shape.exportBrepToString(), shape
        )
        for name, pose in poses.items():
            self.assertTrue(self.doc.getObject(name).Placement.isSame(pose, 1e-7))

    def test_alternative_failure_restores_sensor_metadata_and_common_pitch(self):
        import json

        from gondola.parts import propulsion_wiring
        from gondola.parts.instrument_mount import set_pitch
        from gondola.validation import optical

        set_pitch(self.doc, 11)
        propulsion = self.doc.MainPropulsionModule.getGlobalPlacement()
        stage = self.doc.InstrumentPitchStage.getGlobalPlacement()
        for prefix, sign in propulsion_wiring.PREFIX_SIGNS:
            obj = self.doc.getObject(prefix + "PhaseLeadLoopReserve")
            obj.Shape = propulsion_wiring.route_geometry(sign, propulsion, stage)[
                "shape"
            ]
            obj.WiringContract = json.dumps(
                propulsion_wiring.route_contract(sign, propulsion, stage),
                sort_keys=True,
            )
        self.doc.recompute()
        before = optical._saved_sensor_state(self.doc)
        visited = []

        def probe(doc, physical, kit, *, profile):
            self.assertEqual(float(doc.InstrumentPitchStage.Pitch), 11)
            visited.append(profile.key)
            set_pitch(doc, -7)
            if len(visited) == 2:
                raise RuntimeError("Deliberate alternative failure")
            return {"passed": True}

        with (
            patch.object(optical, "_placement_checks", side_effect=probe),
            patch.object(
                optical, "mounting_service_check", return_value={"passed": True}
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Deliberate"):
                optical.mtf_sensor_check(self.doc)
        self.assertEqual(visited, ["MTF02P", "MTF01P"])
        self.assertEqual(float(self.doc.InstrumentPitchStage.Pitch), 11)
        after = optical._saved_sensor_state(self.doc)
        for name, properties in before.items():
            for key, value in properties.items():
                if key == "Shape":
                    self.assertLess(abs(value.cut(after[name][key]).Volume), 1e-7)
                    self.assertLess(abs(after[name][key].cut(value).Volume), 1e-7)
                elif key == "Placement":
                    self.assertTrue(value.isSame(after[name][key], 1e-7))
                else:
                    self.assertEqual(value, after[name][key], (name, key))

    def test_unknown_external_stock_is_not_filtered_from_field(self):
        from gondola.validation.optical_envelopes import external_field_bound
        from gondola.validation.wiring import collision_hits

        bound, _ = external_field_bound(self.doc.OpticalFlowModule)
        point = self.doc.OpticalSensorFrame.getGlobalPlacement().multVec(
            App.Vector(0, 0, 80)
        )
        block = Part.makeSphere(0.2, point)
        self.assertGreater(bound.common(block).Volume, 0.03)
        hits = collision_hits(bound, {"UnknownBlock": block}, tolerance=1e-5)
        self.assertEqual([row["object"] for row in hits], ["UnknownBlock"])

    def test_mtf01_connector_obstruction_is_detected_on_common_stage(self):
        from gondola.cad import belongs_to_group, world_shape
        from gondola.contracts.optical_sensors import get_sensor_profile
        from gondola.parts import instrument_mount, optical_sensor
        from gondola.validation import optical

        profile = get_sensor_profile("MTF01P")
        optical_sensor.apply_profile(self.doc, profile)
        instrument_mount.set_pitch(self.doc, 0)
        r = self.doc.DesignRegistry
        physical = (
            list(r.PrintedParts)
            + list(r.HardwareParts)
            + list(r.ReferenceParts)
            + list(r.TapeReferences)
        )
        kit = [
            obj for obj in physical if belongs_to_group(obj, self.doc.OpticalFlowModule)
        ]
        point = self.doc.OpticalSensorFrame.getGlobalPlacement().multVec(
            App.Vector(
                0, profile.size_mm[1] / 2 + 5, optical_sensor.SENSOR_BOTTOM_Z + 8
            )
        )
        sphere = Part.makeSphere(0.25, point)
        self.assertGreater(
            world_shape(self.doc.MTF02PConnectorReserve).common(sphere).Volume, 0.06
        )
        self.assertTrue(
            all(world_shape(obj).common(sphere).Volume < 1e-5 for obj in physical)
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
        with patch.object(optical, "PITCH_SAMPLE_ANGLES", (0,)):
            result = optical._placement_checks(self.doc, physical, kit, profile=profile)
        self.assertFalse(result["passed"])
        row = next(
            row
            for row in result["sampled_attitudes"][0][
                "connector_reserved_space_clearances"
            ]
            if row["object"] == reserve.Name
        )
        self.assertFalse(row["passed"])
        self.assertGreater(row["intersection_mm3"], 0.06)

    def test_integral_pad_or_bridge_load_path_cannot_be_removed(self):
        from gondola.validation.optical import _rigid_interface_checks

        self.assertTrue(_rigid_interface_checks(self.doc)["passed"])
        part = self.doc.ElectronicsMount
        part.Shape = part.Shape.cut(Part.makeBox(2, 1, 2, App.Vector(-1, -1, 42)))
        self.assertFalse(_rigid_interface_checks(self.doc)["passed"])
