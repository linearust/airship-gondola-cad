"""Compact carrier interfaces, source-bound carbon hardware and device axes."""

import json
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class EquipmentMountShapeTests(unittest.TestCase):
    def test_all_carriers_clear_the_rail_in_both_clamped_lateral_poses(self):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail
        from gondola.validation.geometry import intersection_volume

        stations = {station.object_name: station for station in MODULE_STATIONS}
        for kind in mounts.MOUNT_NAMES:
            station = stations[kind.capitalize() + "EquipmentModule"]
            for side in (-1, 1):
                body = mounts.mount_shape(kind).copy()
                body.Placement = App.Placement(
                    App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                ).multiply(body.Placement)
                with self.subTest(kind=kind, clamped_side=side):
                    self.assertLess(intersection_volume(body, rail.rail_shape()), 1e-6)

    def test_role_carriers_are_compact_single_solids_with_distinct_skus(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import stack_interface

        for kind, expected_size in (
            ("battery", (22, 68)),
            ("accessory", (36, 66)),
            ("electronics", mounts.ELECTRONICS_DECK_SIZE),
        ):
            with self.subTest(kind=kind):
                low = mounts.mount_shape(kind)
                self.assertTrue(low.isValid())
                self.assertEqual(len(low.Solids), 1)
                plate = mounts.carrier_plate_shape(kind)
                self.assertAlmostEqual(plate.BoundBox.XLength, expected_size[0])
                self.assertAlmostEqual(plate.BoundBox.YLength, expected_size[1])
                self.assertEqual(
                    mounts.mount_contract(kind)["print_sku"], mounts.PRINT_SKUS[kind]
                )
                self.assertLess(
                    abs(low.cut(stack_interface.carrier_shape(kind)).Volume), 1e-6
                )
        self.assertEqual(len(set(mounts.PRINT_SKUS.values())), 3)
        fc = mounts.carrier_plate_shape("electronics")
        self.assertFalse(
            fc.isInside(App.Vector(12, 12, mounts.FC_SADDLE_BOTTOM_Z + 1), 1e-6, True)
        )
        for kind in ("battery", "electronics"):
            variant = stack_interface.carrier_shape(kind, with_optical=True)
            self.assertTrue(variant.isValid())
            self.assertEqual(len(variant.Solids), 1)
            self.assertLess(abs(mounts.mount_shape(kind).cut(variant).Volume), 1e-6)
            self.assertGreater(variant.Volume, mounts.mount_shape(kind).Volume)
            self.assertNotEqual(
                stack_interface.carrier_print_sku(kind, True), mounts.PRINT_SKUS[kind]
            )

    def test_printed_bores_preserve_complete_annuli_and_detect_damage(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_bore_checks

        for kind, count in (("battery", 0), ("electronics", 2), ("accessory", 6)):
            shape = mounts.mount_shape(kind)
            report = carrier_bore_checks(shape, kind)
            self.assertTrue(report["passed"], report)
            self.assertEqual(report["physical_plate_hole_count"], count)
            for row in mounts.carrier_hole_rows(kind):
                centre = row["centre_xy_mm"]
                bottom = mounts.carrier_plate_bottom(kind)
                with self.subTest(kind=kind, centre=centre):
                    obstruction = Part.makeCylinder(0.4, 2, App.Vector(*centre, bottom))
                    self.assertFalse(
                        carrier_bore_checks(shape.fuse(obstruction), kind)["passed"]
                    )
                    notch = Part.makeCylinder(
                        0.2, 2, App.Vector(centre[0] + 2, centre[1], bottom)
                    )
                    self.assertFalse(
                        carrier_bore_checks(shape.cut(notch), kind)["passed"]
                    )

    def test_unbolted_saddle_pads_are_still_structural_contact_surfaces(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import stock_adapter
        from gondola.validation.equipment import carrier_bore_checks

        shape = mounts.mount_shape("electronics")
        report = carrier_bore_checks(shape, "electronics")
        self.assertEqual(len(report["unbolted_printed_contact_pads"]), 2)
        for row in report["unbolted_printed_contact_pads"]:
            x, y = row["centre_xy_mm"]
            notch = Part.makeCylinder(
                0.4, 2, App.Vector(x, y, stock_adapter.SADDLE_BOTTOM_Z)
            )
            self.assertFalse(
                carrier_bore_checks(shape.cut(notch), "electronics")["passed"]
            )

    def test_pas_axes_are_device_local_then_translated_to_accessory_support(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.parts import equipment_mounts as mounts

        self.assertEqual(mounts.PAS_HOLE_CENTRES, interfaces.PAS_HOLE_CENTRES)
        self.assertEqual(
            mounts.mount_hole_centres("electronics"), mounts.FC_HOLE_CENTRES
        )
        self.assertEqual(mounts.mount_hole_centres("battery"), ())
        cx, cy = mounts.NAVIGATION_CENTRE_XY
        self.assertEqual(
            mounts.mount_hole_centres("accessory"),
            tuple((cx + x, cy + y) for x, y in interfaces.PAS_HOLE_CENTRES),
        )
        self.assertEqual(len(mounts.standard_hole_rows("accessory")), 4)
        self.assertEqual(mounts.standard_hole_rows("battery"), [])
        self.assertEqual(mounts.standard_hole_rows("electronics"), [])

    def test_continuous_adhesive_regions_retain_real_material(self):
        from gondola.parts import equipment_mounts as mounts

        regions = [
            ("battery", centre, size)
            for centre, size in mounts.BATTERY_ADHESIVE_REGIONS
        ]
        regions += [
            ("accessory", mounts.NAVIGATION_CENTRE_XY, mounts.GPS_ADHESIVE_SIZE),
            ("accessory", mounts.RADIO_CENTRE_XY, mounts.RADIO_ADHESIVE_SIZE),
        ]
        self.assertEqual(
            sum(size[0] * size[1] for _, size in mounts.BATTERY_ADHESIVE_REGIONS), 756
        )
        for kind, centre, size in regions:
            pad = Part.makeBox(
                *size,
                2,
                App.Vector(
                    centre[0] - size[0] / 2,
                    centre[1] - size[1] / 2,
                    mounts.carrier_plate_bottom(kind),
                ),
            )
            self.assertLess(abs(pad.cut(mounts.mount_shape(kind)).Volume), 1e-6)

    def test_ordinary_m2_heads_fit_spare_holes_without_touching_shoe_or_rail(self):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import purchased_hardware, rail

        station = next(
            row
            for row in MODULE_STATIONS
            if row.object_name == "AccessoryEquipmentModule"
        )
        for row in mounts.standard_hole_rows("accessory"):
            screw = purchased_hardware.screw_shape(8)
            screw.translate(App.Vector(*row["centre_xy_mm"], mounts.DECK_BOTTOM_Z))
            self.assertLess(screw.common(mounts.mount_shape("accessory")).Volume, 1e-6)
            for side in (-1, 1):
                placed = screw.copy()
                placed.Placement = App.Placement(
                    App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                ).multiply(placed.Placement)
                self.assertGreaterEqual(
                    placed.distToShape(rail.rail_shape())[0], 1.0 - 1e-6
                )

    def test_top_radio_requires_correct_contact_face_and_adhesive_gap(self):
        from gondola.parts import equipment_envelopes as devices
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment_options import adhesive_support_check

        support = mounts.mount_shape("accessory")
        body = devices.radio_envelope_shape()

        def check(shape, face="top"):
            return adhesive_support_check(
                support,
                shape,
                mounts.RADIO_CENTRE_XY,
                mounts.RADIO_ADHESIVE_SIZE,
                face=face,
            )

        report = check(body)
        self.assertTrue(report["passed"], report)
        self.assertAlmostEqual(report["adhesive_allowance_mm"], 1)
        self.assertFalse(check(body, "bottom")["passed"])
        for shift in (0.5, 1, 2, -1):
            displaced = body.copy()
            displaced.translate(App.Vector(0, 0, shift))
            self.assertFalse(check(displaced)["passed"])
        with self.assertRaises(ValueError):
            check(body, "top_typo")

    def test_radio_removal_is_outward_after_arbitrary_parent_rotation(self):
        from gondola.parts import equipment_envelopes as devices
        from gondola.parts import equipment_layout, equipment_mounts
        from gondola.validation.geometry import translation_sweep

        body = devices.radio_envelope_shape()
        support = equipment_mounts.mount_shape("accessory").copy()
        local_travel = equipment_layout.device_removal_vector("ModuleRadioEnvelope")
        self.assertEqual(tuple(local_travel), (0, 0, 32))
        placement = App.Placement(
            App.Vector(12, 30, 60), App.Rotation(App.Vector(1, 2, 3), 37)
        )
        for shape in (body, support):
            shape.Placement = placement.multiply(shape.Placement)
        travel = placement.Rotation.multVec(App.Vector(*local_travel))
        sweep, _ = translation_sweep(body, tuple(travel))
        self.assertLess(sweep.common(support).Volume, 1e-6)
        wrong, _ = translation_sweep(body, tuple(-travel))
        self.assertGreater(wrong.common(support).Volume, 100)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class FCInstallationTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import create_group
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts.equipment_envelopes import build_equipment
        from gondola.parts.equipment_mounts import build_mount

        self.doc = App.newDocument("FCInstallationRegression")
        self.addCleanup(App.closeDocument, self.doc.Name)
        groups = {}
        for station in MODULE_STATIONS:
            group = create_group(self.doc, station.object_name, station.object_name)
            group.Placement = App.Placement(
                App.Vector(station.x_mm, 0, 0),
                App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
            )
            groups[station.object_name] = group
        for kind in ("battery", "electronics", "accessory"):
            build_mount(self.doc, groups[kind.capitalize() + "EquipmentModule"], kind)
        build_equipment(
            self.doc,
            groups["BatteryEquipmentModule"],
            groups["ElectronicsEquipmentModule"],
            groups["AccessoryEquipmentModule"],
        )
        self.doc.recompute()

    def test_print_metadata_uses_role_skus_without_claiming_half_turn_symmetry(self):
        from gondola.parts import equipment_mounts as mounts

        for kind, name in mounts.MOUNT_NAMES.items():
            obj = self.doc.getObject(name)
            self.assertEqual(obj.PrintSKU, mounts.PRINT_SKUS[kind])
            self.assertFalse(obj.IntegralOpticalSupport)
            self.assertEqual(obj.MountKind, kind)
            self.assertFalse(obj.HalfTurnSymmetric)
            self.assertEqual(
                [(point.x, point.y, point.z) for point in obj.CarrierHoleCentres],
                [
                    (*row["centre_xy_mm"], mounts.carrier_plate_bottom(kind))
                    for row in mounts.carrier_hole_rows(kind)
                ],
            )
            self.assertAlmostEqual(
                obj.EquipmentFaceZ.Value, mounts.support_face_z(kind)
            )
            contract = json.loads(obj.MountContract)
            self.assertEqual(
                len(contract["carrier_holes"]),
                {"battery": 0, "electronics": 2, "accessory": 6}[kind],
            )
            self.assertEqual(
                contract["mount_hole_centres_xy_mm"],
                [list(xy) for xy in mounts.mount_hole_centres(kind)],
            )

    def test_both_battery_references_follow_the_same_raised_deck_datum(self):
        from gondola.cad import world_shape
        from gondola.parts import equipment_layout, equipment_mounts

        for name in ("ModuleBatteryEnvelope", "MaximumBatteryEnvelope"):
            obj = self.doc.getObject(name)
            group = obj.getParentGeoFeatureGroup()
            expected = (
                group.getGlobalPlacement()
                .multVec(App.Vector(0, 0, equipment_layout.adhesive_bottom()))
                .z
            )
            self.assertAlmostEqual(world_shape(obj).BoundBox.ZMin, expected)
        self.assertAlmostEqual(
            self.doc.ModuleBatteryEnvelope.BottomZ.Value,
            equipment_mounts.SUPPORT_FACE_Z + equipment_mounts.ADHESIVE_ALLOWANCE,
        )

    def test_native_hole_axis_metadata_follows_shared_support(self):
        from gondola.parts import equipment_mounts as mounts

        centres = mounts.FC_HOLE_CENTRES
        self.assertEqual(
            [
                (point.x, point.y, point.z)
                for point in self.doc.ElectronicsMount.MountHoleCentres
            ],
            [(x, y, mounts.carrier_plate_bottom("electronics")) for x, y in centres],
        )
        for name, expected in (
            ("ModuleFCEnvelope", mounts.FC_HOLE_CENTRES),
            (
                "ModulePASEnvelope",
                mounts.mount_hole_centres("accessory"),
            ),
        ):
            with self.subTest(device=name):
                obj = self.doc.getObject(name)
                self.assertEqual(
                    [(point.x, point.y, point.z) for point in obj.VerifiedHoleAxesXY],
                    [(x, y, 0) for x, y in expected],
                )

    def test_native_board_pose_preserves_heading_after_carrier_turn(self):
        from gondola.validation.equipment import fc_installation_check

        result = fc_installation_check(self.doc)
        self.assertTrue(result["passed"], result)

    def test_unchanged_board_shape_cannot_hide_stale_controller_identity(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.validation.baseline import procurement_and_scope_metadata
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        self.assertIn(interfaces.FC_MODEL, board.Label)
        original = board.Shape.copy()
        contract = json.loads(json.dumps(interfaces.flight_controller_contract()))
        self.assertIn("FlightControllerContract", procurement_and_scope_metadata(board))
        contract["model"] = "MicoAir743v2-AIO-35A"
        board.FlightControllerContract = json.dumps(contract)
        result = fc_installation_check(self.doc)
        self.assertFalse(result["native_flight_controller_contract_matches"])
        self.assertFalse(result["passed"])
        self.assertLess(abs(board.Shape.cut(original).Volume), 1e-6)
        self.assertLess(abs(original.cut(board.Shape).Volume), 1e-6)

    def test_missing_or_malformed_controller_contract_is_rejected(self):
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        for value in ("{", "null", "[]"):
            with self.subTest(value=value):
                board.FlightControllerContract = value
                self.assertFalse(fc_installation_check(self.doc)["passed"])
        board.removeProperty("FlightControllerContract")
        self.assertFalse(fc_installation_check(self.doc)["passed"])

    def test_controller_firmware_or_input_evidence_cannot_silently_change(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.validation.equipment import fc_installation_check

        for mutation in ("firmware", "input_claim", "compatibility"):
            with self.subTest(mutation=mutation):
                contract = json.loads(
                    json.dumps(interfaces.flight_controller_contract())
                )
                electrical = contract["electrical"]
                if mutation == "firmware":
                    electrical["esc_firmware"] = "Bluejay"
                elif mutation == "input_claim":
                    electrical["input_claims"]["manual_text"]["cells"] = [2, 6]
                else:
                    electrical["compatibility_status"] = "verified"
                self.doc.ModuleFCEnvelope.FlightControllerContract = json.dumps(
                    contract
                )
                result = fc_installation_check(self.doc)
                self.assertFalse(result["native_flight_controller_contract_matches"])
                self.assertFalse(result["passed"])

    def test_symmetric_board_solid_cannot_hide_reversed_installation(self):
        from gondola.cad import world_shape
        from gondola.print_export import geometry_comparison
        from gondola.validation.equipment import fc_installation_check

        board = self.doc.ModuleFCEnvelope
        original = world_shape(board)
        board.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), -45)
        self.doc.recompute()
        self.assertLess(
            geometry_comparison(world_shape(board), original)["difference_mm3"],
            1e-6,
        )
        result = fc_installation_check(self.doc)
        self.assertFalse(result["native_board_placement_matches"])
        self.assertFalse(result["passed"])

    def test_wrong_parent_turn_or_native_orientation_marker_is_rejected(self):
        from gondola.validation.equipment import fc_installation_check

        self.doc.ModuleFCEnvelope.InstallationYawInCarrier = 0
        self.assertFalse(fc_installation_check(self.doc)["passed"])
        self.doc.ModuleFCEnvelope.InstallationYawInCarrier = 180
        self.doc.ElectronicsEquipmentModule.Placement.Rotation = App.Rotation()
        self.assertFalse(fc_installation_check(self.doc)["passed"])


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class StockAdapterInstallationTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import create_group
        from gondola.parts import equipment_envelopes, equipment_mounts, stock_adapter

        self.doc = App.newDocument("StockAdapterInstallation")
        self.addCleanup(App.closeDocument, self.doc.Name)
        groups = {}
        for kind in ("battery", "electronics", "accessory"):
            name = kind.capitalize() + "EquipmentModule"
            groups[kind] = create_group(self.doc, name, name)
        groups["electronics"].Placement = App.Placement(
            App.Vector(-54, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        printed = [
            equipment_mounts.build_mount(self.doc, groups[kind], kind)
            for kind in groups
        ]
        equipment_envelopes.build_equipment(
            self.doc, groups["battery"], groups["electronics"], groups["accessory"]
        )
        hardware = stock_adapter.build_stock_adapter(self.doc, groups["electronics"])[
            "hardware"
        ]
        registry = self.doc.addObject("App::DocumentObjectGroup", "DesignRegistry")
        for name, objects in (("PrintedParts", printed), ("HardwareParts", hardware)):
            registry.addProperty("App::PropertyLinkListGlobal", name)
            setattr(registry, name, objects)
        self.doc.recompute()

    def test_nominal_bought_plate_and_separate_clamps_do_not_certify_laminate_contact(
        self,
    ):
        from gondola.validation.equipment import stock_adapter_check

        report = stock_adapter_check(self.doc)
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["purchased_parts"]), 13)
        self.assertEqual(len(report["nominal_purchased_bores"]), 12)
        self.assertFalse(report["exact_carbon_contact_qualified"])
        self.assertAlmostEqual(self.doc.StockFCAdapter.ReferenceMassGrams, 0.72)

    def test_shifted_clamp_and_missing_registry_entry_are_rejected(self):
        from gondola.parts import stock_adapter
        from gondola.validation.equipment import stock_adapter_check

        nut = self.doc.getObject(stock_adapter.NUT_OBJECT_NAMES[0])
        original = App.Placement(nut.Placement)
        try:
            nut.Placement.Base += App.Vector(0, 0, 0.3)
            self.assertFalse(stock_adapter_check(self.doc)["passed"])
        finally:
            nut.Placement = original
        self.doc.DesignRegistry.HardwareParts = [
            obj
            for obj in self.doc.DesignRegistry.HardwareParts
            if obj != self.doc.StockFCAdapter
        ]
        self.assertFalse(stock_adapter_check(self.doc)["passed"])

    def test_mass_and_unsupported_physical_fit_claim_are_rejected(self):
        from gondola.validation.equipment import stock_adapter_check

        self.doc.StockFCAdapter.ReferenceMassGrams = 0.5
        self.assertFalse(stock_adapter_check(self.doc)["passed"])
        self.doc.StockFCAdapter.ReferenceMassGrams = 0.72
        self.doc.StockFCAdapter.PhysicalFitVerified = True
        self.assertFalse(stock_adapter_check(self.doc)["passed"])

    def test_integral_carrier_remains_a_service_obstacle_and_proxy_cannot_hide_a_larger_body(
        self,
    ):
        from gondola.cad import world_shape
        from gondola.parts import stack_interface
        from gondola.validation.equipment import device_service_check

        parent = self.doc.ElectronicsEquipmentModule
        carrier = self.doc.ElectronicsMount
        carrier.Shape = stack_interface.carrier_shape("electronics", True)
        body = self.doc.ModuleFCEnvelope
        objects = [carrier, body, *self.doc.DesignRegistry.HardwareParts]

        def check():
            return device_service_check(
                self.doc,
                body.Name,
                objects,
                {obj.Name: world_shape(obj) for obj in objects},
            )

        report = check()
        self.assertTrue(report["passed"], report)
        self.assertTrue(report["integral_carrier_remains_obstacle"])
        self.assertFalse(report["complete_optical_tower_removed"])
        blocker = self.doc.addObject("Part::Feature", "ServiceBlocker")
        parent.addObject(blocker)
        blocker.Shape = Part.makeBox(2, 2, 2, App.Vector(-30, 30, 40))
        objects.append(blocker)
        self.assertFalse(check()["passed"])
        objects.remove(blocker)
        enlarged = world_shape(body)
        enlarged.Placement = (
            parent.getGlobalPlacement().inverse().multiply(enlarged.Placement)
        )
        body.Placement = App.Placement()
        body.Shape = enlarged.fuse(Part.makeBox(2, 2, 2, App.Vector(25, 0, 26)))
        report = check()
        self.assertGreater(report["actual_device_outside_service_proxy_mm3"], 1)
        self.assertFalse(report["passed"])


if __name__ == "__main__":
    unittest.main()
