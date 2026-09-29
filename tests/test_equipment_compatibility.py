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
        total_overlap = 0
        for centre, size in mounts.RADIO_ADHESIVE_REGIONS:
            with self.subTest(patch=centre):
                report = adhesive_support_check(
                    support, body, centre, size, face="bottom"
                )
                self.assertTrue(report["passed"])
                self.assertEqual(report["support_face"], "bottom")
                self.assertAlmostEqual(report["continuous_support_area_mm2"], 60)
                self.assertAlmostEqual(report["nominal_supported_overlap_mm2"], 60)
                total_overlap += report["nominal_supported_overlap_mm2"]
                x, y = centre
                damaged = support.cut(
                    Part.makeBox(
                        2,
                        2,
                        mounts.DECK_THICKNESS + 2,
                        App.Vector(x - 1, y - 1, mounts.DECK_BOTTOM_Z - 1),
                    )
                )
                self.assertFalse(
                    adhesive_support_check(damaged, body, centre, size, face="bottom")[
                        "passed"
                    ]
                )
                displaced = body.copy()
                # Partial overlap must fail even when some contact remains.
                displaced.translate(App.Vector(8 if x < 26 else -6, 0, 0))
                shifted = adhesive_support_check(
                    support, displaced, centre, size, face="bottom"
                )
                self.assertGreater(shifted["nominal_supported_overlap_mm2"], 0)
                self.assertLess(shifted["nominal_supported_overlap_mm2"], 60)
                self.assertFalse(shifted["passed"])
        self.assertAlmostEqual(total_overlap, 120)

    def test_all_combinations_and_blocked_alternative_connector_lane(self):
        from gondola.cad import world_shape
        from gondola.validation.equipment_options import compatibility_check

        result = compatibility_check(self.doc)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["combinations"]), 3)
        for row in result["combinations"]:
            self.assertEqual(len(row["optical_compatibility"]["hosts_and_sensors"]), 4)
            if row["navigation_model"] == "MGF10A":
                antenna = row["direct_antenna"]["optical_clearance"]
                self.assertEqual(
                    antenna["permitted_optical_hosts"], ["BatteryEquipmentModule"]
                )
                self.assertEqual(
                    antenna["blocked_optical_hosts"], ["ElectronicsEquipmentModule"]
                )
                self.assertEqual(len(antenna["hosts_and_sensors"]), 4)
                for pose_row in antenna["hosts_and_sensors"]:
                    self.assertEqual(
                        pose_row["passed"], pose_row["host"] == "BatteryEquipmentModule"
                    )
            services = {
                service["device"]: service
                for service in row["bare_device_service_after_tower_release"]
            }
            self.assertEqual(
                services["ModuleRadioEnvelope"]["local_removal_vector_mm"],
                (0.0, 0.0, -32.0),
            )
            self.assertTrue(services["ModuleRadioEnvelope"]["bench_access_required"])
            self.assertIn(
                "TapeWing0L",
                services["ModuleRadioEnvelope"][
                    "off_carrier_parts_excluded_for_bench_service"
                ],
            )
            self.assertEqual(
                services["ModulePASEnvelope"]["local_removal_vector_mm"],
                (0.0, 0.0, 32.0),
            )
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

    def test_direct_helix_requires_clear_battery_optical_host(self):
        from gondola.cad import placed_shape
        from gondola.contracts.equipment_options import get_navigation_profile
        from gondola.parts import wiring_reserves
        from gondola.validation.equipment_options import (
            _optical_option_check,
            _optical_screens,
        )

        screens = _optical_screens(self.doc)
        direct = wiring_reserves.direct_antenna_reserve_shape(
            get_navigation_profile("MGF10A")
        )
        direct = placed_shape(
            direct, self.doc.AccessoryEquipmentModule.getGlobalPlacement()
        )
        cache = {}
        for host, expected in (
            ("BatteryEquipmentModule", True),
            ("ElectronicsEquipmentModule", False),
        ):
            with self.subTest(installed_host=host):
                report = _optical_option_check(
                    screens,
                    {"NavigationDirectAntennaReserve": direct},
                    antenna=True,
                    navigation_key="MGF10A",
                    required_host=host,
                    validation_cache=cache,
                )
                self.assertEqual(report["passed"], expected, report)
                self.assertEqual(report["installed_host_passed"], expected)
                self.assertEqual(report["required_installed_optical_host"], host)
                self.assertEqual(
                    report["geometrically_clear_optical_hosts"],
                    ["BatteryEquipmentModule"],
                )

        # The known MG-F10-A restriction must not silently qualify other
        # antenna profiles when the same physical obstacle blocks their FC host.
        unknown = _optical_option_check(
            screens,
            {"OtherNavigationAntenna": direct},
            antenna=True,
            navigation_key="UNKNOWN",
            required_host="BatteryEquipmentModule",
        )
        self.assertFalse(unknown["passed"])
        self.assertEqual(len(unknown["permitted_optical_hosts"]), 2)

    def test_detached_radio_service_still_rejects_an_attached_carrier_obstacle(self):
        from gondola.parts import equipment_envelopes
        from gondola.validation.equipment import mounting_check

        body = equipment_envelopes.radio_envelope_shape()
        bounds = body.BoundBox
        blocker = self.doc.addObject("Part::Feature", "CarrierServiceBlocker")
        self.doc.AccessoryEquipmentModule.addObject(blocker)
        blocker.Shape = Part.makeBox(
            2,
            2,
            2,
            App.Vector(bounds.Center.x - 1, bounds.Center.y - 1, bounds.ZMin - 12),
        )
        original = list(self.doc.DesignRegistry.ReferenceParts)
        try:
            self.doc.DesignRegistry.ReferenceParts = original + [blocker]
            result = mounting_check(self.doc)
            service = next(
                row
                for row in result["device_service"]
                if row["device"] == "ModuleRadioEnvelope"
            )
            self.assertTrue(service["bench_access_required"])
            self.assertFalse(service["passed"])
            self.assertIn(blocker.Name, service["collisions"])
            self.assertNotIn(
                blocker.Name, service["off_carrier_parts_excluded_for_bench_service"]
            )
            self.assertIn(
                "TapeWing0L", service["off_carrier_parts_excluded_for_bench_service"]
            )
        finally:
            self.doc.DesignRegistry.ReferenceParts = original
            self.doc.removeObject(blocker.Name)


if __name__ == "__main__":
    unittest.main()
