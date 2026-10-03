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
        self.assertTrue(result["all_options_screened"])
        self.assertTrue(result["selected_combination_passed"])
        self.assertEqual(
            result["selected_combination"],
            {"navigation_model": "PAS", "radio_model": "LR24FMINI"},
        )
        self.assertFalse(result["all_options_supported"])
        for row in result["combinations"]:
            self.assertEqual(len(row["optical_compatibility"]["sensor_screens"]), 2)
            if row["navigation_model"] == "MGF10A":
                antenna = row["direct_antenna"]["optical_clearance"]
                self.assertEqual(len(antenna["sensor_screens"]), 2)
                self.assertFalse(row["passed"])
                self.assertTrue(row["base_installation_passed"])
                self.assertFalse(row["direct_antenna"]["passed"])
                self.assertTrue(row["remote_antenna"]["supported_conditionally"])
                self.assertFalse(row["remote_antenna"]["location_modeled"])
                self.assertTrue(
                    any(
                        not pose_row["passed"] for pose_row in antenna["sensor_screens"]
                    )
                )
            else:
                self.assertTrue(row["passed"])
            if row["navigation_model"] == "PAS":
                for screen in row["optical_compatibility"]["sensor_screens"]:
                    refined = next(
                        bound
                        for bound in screen["continuous_external_bounds"]
                        if bound["bound"] == "Instrument/FCWiringClearanceReserve"
                    )
                    pas = next(
                        clearance
                        for clearance in refined["clearances"]
                        if clearance["object"] == "ModulePASEnvelope"
                    )
                    self.assertGreater(
                        pas["conservative_bound_clearance"]["intersection_mm3"], 100
                    )
                    self.assertTrue(pas["actual_stock_pitch_certificate"]["passed"])
            services = {
                service["device"]: service for service in row["bare_device_service"]
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

    def test_direct_helix_is_screened_at_actual_attachment(self):
        from gondola.cad import placed_shape
        from gondola.contracts.equipment_options import get_navigation_profile
        from gondola.parts import wiring_reserves
        from gondola.validation.equipment_options import (
            _optical_option_check,
            _optical_screens,
        )

        screens = _optical_screens(self.doc)
        direct = placed_shape(
            wiring_reserves.direct_antenna_reserve_shape(
                get_navigation_profile("MGF10A")
            ),
            self.doc.AccessoryEquipmentModule.getGlobalPlacement(),
        )
        actual = screens[0]["attachment"]
        self.assertEqual(actual["native_parent"], "InstrumentPitchStage")
        self.assertEqual(actual["fixed_sensor_frame"], "OpticalSensorFrame")
        self.assertEqual(actual["rail_module"], "ElectronicsEquipmentModule")
        self.assertEqual(actual["instrument_pitch_range_deg"], (-20.0, 20.0))
        for required, expected in (
            (actual, True),
            ({**actual, "native_parent": "BatteryEquipmentModule"}, False),
            ({**actual, "instrument_pitch_range_deg": (0.0, 0.0)}, False),
        ):
            report = _optical_option_check(
                screens,
                {},
                required_mount=required,
            )
            self.assertEqual(report["passed"], expected, report)
            self.assertEqual(report["installed_attachment_matches"], expected)
        # The direct antenna reserve remains a real geometric input, even when
        # the declared attachment is the correct common instrument stage.
        antenna = _optical_option_check(
            screens,
            {"NavigationDirectAntennaReserve": direct},
            antenna=True,
            required_mount=actual,
        )
        self.assertTrue(antenna["installed_attachment_matches"])
        self.assertFalse(antenna["passed"])
        # Unknown obstacles remain geometric inputs; no profile-name allowlist.
        blocked = _optical_option_check(
            screens, {"Unknown": screens[0]["continuous_field"]}
        )
        self.assertFalse(blocked["passed"])

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


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalEquipmentScreenTests(unittest.TestCase):
    def native_optical(self):
        from gondola.config import BASELINE_FILE
        from gondola.provenance import file_sha256

        before = file_sha256(BASELINE_FILE)
        doc = App.openDocument(str(BASELINE_FILE), hidden=True)

        def close_without_saving():
            App.closeDocument(doc.Name)
            self.assertEqual(file_sha256(BASELINE_FILE), before)

        self.addCleanup(close_without_saving)
        return doc

    def test_both_sensor_models_move_the_complete_saved_common_platform(self):
        from gondola.cad import world_shape
        from gondola.parts import instrument_mount
        from gondola.validation.equipment_options import _optical_screens

        doc = self.native_optical()
        screens = _optical_screens(doc)
        self.assertEqual({row["sensor"] for row in screens}, {"MTF01P", "MTF02P"})
        names = {"ElectronicsMount", "ModuleFCEnvelope"}
        for screen in screens:
            attachment = screen["attachment"]
            self.assertEqual(attachment["native_parent"], "InstrumentPitchStage")
            self.assertEqual(attachment["fixed_sensor_frame"], "OpticalSensorFrame")
            self.assertEqual(attachment["rail_module"], "ElectronicsEquipmentModule")
            self.assertEqual(attachment["rail_station_x_mm"], -82)
            self.assertEqual(attachment["instrument_pitch_range_deg"], (-20, 20))
            self.assertTrue(names.issubset(screen["saved_moving_parts"]))
            for name in names:
                self.assertIn("Instrument/" + name, screen["continuous_bounds"])
            for pose in screen["poses"]:
                instrument_mount.set_pitch(doc, pose["instrument_pitch_deg"])
                for name in names:
                    with self.subTest(
                        sensor=screen["sensor"],
                        angle=pose["instrument_pitch_deg"],
                        object=name,
                    ):
                        actual = world_shape(doc.getObject(name))
                        self.assertLess(
                            pose["physical"][name].cut(actual).Volume
                            + actual.cut(pose["physical"][name]).Volume,
                            1e-7,
                        )
                self.assertIn("FCWiringClearanceReserve", pose["instrument_reserves"])
                self.assertNotIn("InstrumentMountBase", pose["physical"])
                self.assertNotIn("OpticalMountBase", pose["physical"])
                self.assertNotIn("OpticalFlowModuleRailMountScrew", pose["physical"])

    def test_saved_unknown_moving_stock_is_a_geometric_obstacle_input(self):
        from gondola.cad import world_shape
        from gondola.validation.equipment_options import (
            _optical_option_check,
            _optical_screens,
        )

        doc = self.native_optical()
        unknown = doc.addObject("Part::Feature", "UnknownInstrumentStock")
        doc.InstrumentPitchStage.addObject(unknown)
        unknown.Shape = Part.makeBox(2, 2, 2, App.Vector(40, 0, 25))
        doc.DesignRegistry.ReferenceParts = [
            *doc.DesignRegistry.ReferenceParts,
            unknown,
        ]
        nominal = world_shape(unknown)
        unknown.Placement.Base.x += 20
        doc.recompute()
        screens = _optical_screens(doc)
        obstacle = world_shape(unknown)
        self.assertGreater(obstacle.Volume, 0)
        self.assertAlmostEqual(nominal.common(obstacle).Volume, 0)
        result = _optical_option_check(screens, {"UnknownHardwareObstacle": obstacle})
        self.assertFalse(result["passed"])
        self.assertTrue(
            all(
                any(
                    hit["moving"] == "UnknownInstrumentStock"
                    and hit["object"] == "UnknownHardwareObstacle"
                    for pose in row["sampled_attitudes"]
                    for hit in pose["collisions"]
                )
                for row in result["sensor_screens"]
            )
        )

    def test_screen_rejects_missing_hardware_metadata_and_independent_controls(self):
        from gondola.validation.equipment_options import _optical_screens

        doc = self.native_optical()
        frame = doc.OpticalSensorFrame
        frame.addProperty("App::PropertyAngle", "Pitch")
        with self.assertRaises(ValueError):
            _optical_screens(doc)
        frame.removeProperty("Pitch")
        obj = doc.ElectronicsMount
        sku = obj.PrintSKU
        obj.PrintSKU = "UniversalCarrier"
        with self.assertRaises(ValueError):
            _optical_screens(doc)
        obj.PrintSKU = sku
        registered = list(doc.DesignRegistry.PrintedParts)
        doc.DesignRegistry.PrintedParts = [part for part in registered if part != obj]
        with self.assertRaises(ValueError):
            _optical_screens(doc)
        doc.DesignRegistry.PrintedParts = registered
        doc.removeObject(obj.Name)
        with self.assertRaises(ValueError):
            _optical_screens(doc)

    def test_unknown_moving_stock_between_samples_fails_continuous_certificate(self):
        from gondola.cad import placed_shape, world_shape
        from gondola.parts import instrument_mount
        from gondola.validation.equipment_options import (
            _optical_option_check,
            _optical_screens,
        )

        doc = self.native_optical()
        unknown = doc.addObject("Part::Feature", "UnknownInstrumentStock")
        doc.InstrumentPitchStage.addObject(unknown)
        unknown.Shape = Part.makeSphere(0.5, App.Vector(200, 40, 8))
        doc.DesignRegistry.ReferenceParts = [
            *doc.DesignRegistry.ReferenceParts,
            unknown,
        ]
        doc.recompute()
        screens = _optical_screens(doc)
        relative = world_shape(unknown)
        relative.Placement = (
            doc.InstrumentPitchStage.getGlobalPlacement()
            .inverse()
            .multiply(relative.Placement)
        )
        obstacle = placed_shape(
            relative,
            doc.ElectronicsEquipmentModule.getGlobalPlacement().multiply(
                instrument_mount.stage_placement(5)
            ),
        )
        for screen in screens:
            for pose in screen["poses"]:
                self.assertAlmostEqual(
                    pose["physical"][unknown.Name].common(obstacle).Volume, 0
                )
        report = _optical_option_check(screens, {"BetweenSamples": obstacle})
        self.assertFalse(report["passed"])
        for screen in report["sensor_screens"]:
            bound = next(
                row
                for row in screen["continuous_external_bounds"]
                if row["bound"] == "Instrument/UnknownInstrumentStock"
            )
            self.assertFalse(bound["passed"])
            self.assertFalse(
                bound["clearances"][0]["actual_stock_pitch_certificate"]["passed"]
            )


if __name__ == "__main__":
    unittest.main()
