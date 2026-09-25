"""Native regressions for alternative equipment, tape supports and access lanes."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class EquipmentCompatibilityTests(unittest.TestCase):
    def setUp(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        self.path = BASELINE_FILE
        self.before = file_sha256(self.path)
        self.doc = App.openDocument(str(self.path), hidden=True)
        self.addCleanup(self.close_without_saving)

    def close_without_saving(self):
        from gondola.provenance import file_sha256

        App.closeDocument(self.doc.Name)
        self.assertEqual(file_sha256(self.path), self.before)

    def test_native_profile_identity_and_contract_are_both_checked(self):
        from gondola.validation.equipment_options import source_evidence

        self.assertTrue(source_evidence(self.doc)["passed"])
        changes = (
            (self.doc.ModulePASEnvelope, "NavigationModel", "MGA01"),
            (self.doc.ModulePASEnvelope, "NavigationProfile", "{}"),
            (self.doc.ModuleRadioEnvelope, "RadioModel", "LR900A"),
            (self.doc.ModuleRadioEnvelope, "RadioProfile", "{}"),
        )
        for obj, property_name, changed in changes:
            with self.subTest(property=property_name):
                original = getattr(obj, property_name)
                try:
                    setattr(obj, property_name, changed)
                    self.assertFalse(source_evidence(self.doc)["passed"])
                finally:
                    setattr(obj, property_name, original)

    def test_shortened_connector_lane_cannot_pass_source_evidence(self):
        from gondola.validation.equipment_options import source_evidence

        lane = self.doc.PASConnectorReserve
        original = lane.Shape.copy()
        bounds = original.BoundBox
        try:
            lane.Shape = original.cut(
                Part.makeBox(
                    bounds.XLength + 2,
                    2,
                    bounds.ZLength + 2,
                    App.Vector(bounds.XMin - 1, bounds.Center.y - 1, bounds.ZMin - 1),
                )
            )
            self.assertFalse(source_evidence(self.doc)["passed"])
        finally:
            lane.Shape = original

    def test_radio_support_uses_actual_overlap_and_rejects_missing_material(self):
        from gondola.contracts.equipment_options import get_radio_profile
        from gondola.parts import equipment_envelopes
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment_options import adhesive_support_check
        from gondola.validation.geometry import local_shape

        support = local_shape(self.doc.AccessoryMount)
        body = equipment_envelopes.radio_envelope_shape(get_radio_profile("LR24FMINI"))
        report = adhesive_support_check(
            support, body, mounts.RADIO_CENTRE_XY, mounts.RADIO_ADHESIVE_SIZE
        )
        self.assertTrue(report["passed"])
        self.assertAlmostEqual(report["continuous_support_area_mm2"], 308)
        self.assertAlmostEqual(report["nominal_supported_overlap_mm2"], 308)
        x, y = mounts.RADIO_CENTRE_XY
        damaged = support.cut(
            Part.makeBox(
                2,
                2,
                mounts.DECK_THICKNESS + 2,
                App.Vector(x - 1, y - 1, mounts.DECK_BOTTOM_Z - 1),
            )
        )
        self.assertFalse(
            adhesive_support_check(
                damaged, body, mounts.RADIO_CENTRE_XY, mounts.RADIO_ADHESIVE_SIZE
            )["passed"]
        )
        body.translate(App.Vector(8, 0, 0))
        self.assertFalse(
            adhesive_support_check(
                support, body, mounts.RADIO_CENTRE_XY, mounts.RADIO_ADHESIVE_SIZE
            )["passed"]
        )

    def test_all_combinations_and_blocked_alternative_connector_lane(self):
        from gondola.cad import world_shape
        from gondola.validation.equipment_options import compatibility_check

        result = compatibility_check(self.doc)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["combinations"]), 3)
        for row in result["combinations"]:
            self.assertEqual(len(row["optical_compatibility"]["hosts_and_sensors"]), 4)
        # A physical object introduced midway along the actual lane must fail;
        # validating only lane endpoints or metadata would miss it.
        original = list(self.doc.DesignRegistry.ReferenceParts)
        blocker = self.doc.addObject("Part::Feature", "CompatibilityLaneBlocker")
        centre = world_shape(self.doc.PASConnectorReserve).BoundBox.Center
        blocker.Shape = Part.makeBox(1, 1, 1, centre - App.Vector(0.5, 0.5, 0.5))
        try:
            self.doc.DesignRegistry.ReferenceParts = original + [blocker]
            blocked = compatibility_check(self.doc)
            self.assertFalse(blocked["passed"])
            pas_rows = [
                row
                for row in blocked["combinations"]
                if row["navigation_model"] == "PAS"
            ]
            self.assertTrue(
                all(
                    any(
                        hit["object"] == blocker.Name
                        for hit in row["body_and_connector_collisions"]
                    )
                    for row in pas_rows
                )
            )
        finally:
            self.doc.DesignRegistry.ReferenceParts = original
            self.doc.removeObject(blocker.Name)


if __name__ == "__main__":
    unittest.main()
