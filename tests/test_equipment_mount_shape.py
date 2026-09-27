"""Identical universal carriers with audited holes, contact pads and device axes."""

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
        rail_shape = rail.rail_shape()
        for kind, name in (
            ("battery", "BatteryEquipmentModule"),
            ("electronics", "ElectronicsEquipmentModule"),
            ("accessory", "AccessoryEquipmentModule"),
        ):
            station = stations[name]
            for side in (-1, 1):
                pose = App.Placement(
                    App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                    App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                )
                body = mounts.mount_shape(kind).copy()
                body.Placement = pose.multiply(body.Placement)
                with self.subTest(kind=kind, clamped_side=side):
                    self.assertLess(intersection_volume(body, rail_shape), 1e-6)
        # The accessory plate is above the rail and supported by its integral shoe.
        local = mounts.mount_shape("accessory")
        plate = local.common(Part.makeBox(20, 10, 3, App.Vector(10, -5, 10)))
        self.assertAlmostEqual(plate.BoundBox.ZMin, mounts.DECK_BOTTOM_Z)
        self.assertGreaterEqual(plate.BoundBox.ZMin - rail.HEAD_TOP, 1.8 - 1e-6)

    def test_every_carrier_is_the_same_single_solid_with_a_plain_utility_tab(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.print_export import geometry_comparison

        reference = mounts.mount_shape("battery")
        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            with self.subTest(kind=kind):
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids), 1)
                comparison = geometry_comparison(shape, reference)
                self.assertLess(comparison["difference_mm3"], 1e-6)
                self.assertLess(comparison["bounds_difference_mm"], 1e-6)
                self.assertEqual(
                    mounts.mount_contract(kind)["shared_print_sku"],
                    "UniversalEquipmentCarrier",
                )
                self.assertEqual(
                    mounts.mount_contract(kind)["stack_interface"][
                        "carrier_datum_xy_mm"
                    ],
                    (0.0, 0.0),
                )
                # The complete unperforated utility extension joins the deck;
                # it is not a separate radio part or a set of thin attachment tabs.
                tab = Part.makeBox(22, 27, 2, App.Vector(-11, 27, mounts.DECK_BOTTOM_Z))
                self.assertLess(abs(tab.cut(shape).Volume), 1e-6)
                self.assertLessEqual(shape.BoundBox.XLength, 66)
                self.assertLessEqual(shape.BoundBox.YLength, 87)
                rotated = shape.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 0, 1), 180)
                self.assertGreater(abs(rotated.cut(shape).Volume), 100)

    def test_all_roles_keep_a_full_common_deck_and_all_shared_holes(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import stack_interface

        self.assertEqual(mounts.COMMON_DECK_SIZE, (54.0, 54.0))
        self.assertEqual(len(mounts.common_plate_hole_shapes(0, 2)), 20)
        plate = Part.makeBox(
            54, 54, mounts.DECK_THICKNESS, App.Vector(-27, -27, mounts.DECK_BOTTOM_Z)
        )
        for hole in mounts.common_plate_hole_shapes(
            mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
        ):
            plate = plate.cut(hole)
        # The two existing structural clamp axes cross the square's corners.
        for x, y in stack_interface.CLAMP_CENTRES:
            plate = plate.cut(
                Part.makeCylinder(
                    stack_interface.CLAMP_HOLE_DIAMETER / 2,
                    mounts.DECK_THICKNESS,
                    App.Vector(x, y, mounts.DECK_BOTTOM_Z),
                )
            )
        for kind in mounts.MOUNT_NAMES:
            self.assertLess(abs(plate.cut(mounts.mount_shape(kind)).Volume), 1e-6)
        self.assertEqual(mounts.mount_hole_centres("battery"), ())
        self.assertEqual(
            mounts.mount_hole_centres("electronics"), mounts.FC_HOLE_CENTRES
        )
        self.assertEqual(
            mounts.mount_hole_centres("accessory"), mounts.PAS_HOLE_CENTRES
        )

    def test_standard_holes_have_open_bores_and_full_edge_lands(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail

        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            slots = mounts.standard_hole_shapes(
                kind, mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
            ) + mounts.expansion_hole_shapes(
                mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS
            )
            lands = mounts.standard_hole_shapes(
                kind, mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS, border=1.5
            ) + mounts.expansion_hole_shapes(
                mounts.DECK_BOTTOM_Z, mounts.DECK_THICKNESS, border=1.5
            )
            for slot, outer in zip(slots, lands, strict=True):
                with self.subTest(kind=kind, centre=slot.BoundBox.Center):
                    self.assertLess(abs(slot.common(shape).Volume), 1e-6)
                    self.assertLess(abs(outer.cut(slot).cut(shape).Volume), 1e-6)
                    self.assertLess(abs(slot.common(rail.shoe_shape()).Volume), 1e-6)

    def test_battery_keeps_three_continuous_adhesive_regions(self):
        from gondola.parts import equipment_mounts as mounts

        for centre, size in mounts.BATTERY_ADHESIVE_REGIONS:
            patch = Part.makeBox(
                *size,
                mounts.DECK_THICKNESS,
                App.Vector(
                    centre[0] - size[0] / 2,
                    centre[1] - size[1] / 2,
                    mounts.DECK_BOTTOM_Z,
                ),
            )
            self.assertLess(abs(patch.cut(mounts.mount_shape("battery")).Volume), 1e-6)

    def test_every_carrier_has_a_real_20mm_m2_square_and_no_tie_contract(self):
        from gondola.parts import equipment_mounts as mounts

        for kind in mounts.MOUNT_NAMES:
            contract = mounts.mount_contract(kind)
            self.assertNotIn("generic_fastening", contract)
            patterns = contract["standard_mounting"]["patterns"]
            self.assertEqual(len(patterns), 2)
            common = next(row for row in patterns if row["pitch_mm"] == 20.0)
            self.assertEqual(common["fastener"], "M2")
            self.assertEqual(common["clearance_diameter_mm"], 2.6)
            points = [App.Vector(*xy, 0) for xy in common["centres_xy_mm"]]
            for i in range(4):
                self.assertAlmostEqual((points[i] - points[(i + 1) % 4]).Length, 20.0)
                self.assertAlmostEqual(
                    (points[i] - points[(i + 2) % 4]).Length ** 2, 800.0
                )
            large = patterns[1]
            self.assertEqual(
                (large["pitch_mm"], large["fastener"], large["clearance_diameter_mm"]),
                (30.5, "M3", 3.6),
            )
            self.assertEqual(contract["standard_mounting"]["datum_xy_mm"], (0.0, 0.0))

    def test_ordinary_m2_heads_fit_spare_holes_without_touching_shoe_or_rail(self):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import purchased_hardware, rail

        stations = {row.object_name: row for row in MODULE_STATIONS}
        for kind in mounts.MOUNT_NAMES:
            station = stations[kind.capitalize() + "EquipmentModule"]
            carrier = mounts.mount_shape(kind)
            for row in mounts.standard_hole_rows(kind) + mounts.expansion_hole_rows():
                if row["fastener"] != "M2":
                    continue
                screw = purchased_hardware.screw_shape(8)
                screw.translate(App.Vector(*row["centre_xy_mm"], mounts.DECK_BOTTOM_Z))
                self.assertLess(screw.common(carrier).Volume, 1e-6)
                for side in (-1, 1):
                    placed = screw.copy()
                    placed.Placement = App.Placement(
                        App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                        App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
                    ).multiply(placed.Placement)
                    with self.subTest(kind=kind, hole=row, approach=side):
                        self.assertGreaterEqual(
                            placed.distToShape(rail.rail_shape())[0], 1.0 - 1e-6
                        )

    def test_shared_adhesive_patches_are_intact_and_clear_pas_holes(self):
        from gondola.parts import equipment_mounts as mounts

        shape = mounts.mount_shape("accessory")
        for centre, size in (
            (mounts.NAVIGATION_CENTRE_XY, mounts.GPS_ADHESIVE_SIZE),
            (mounts.RADIO_CENTRE_XY, mounts.RADIO_ADHESIVE_SIZE),
        ):
            pad = Part.makeBox(
                *size,
                mounts.DECK_THICKNESS,
                App.Vector(
                    centre[0] - size[0] / 2,
                    centre[1] - size[1] / 2,
                    mounts.DECK_BOTTOM_Z,
                ),
            )
            self.assertLess(abs(pad.cut(shape).Volume), 1e-6)

    def test_every_carrier_preserves_fc_and_published_pas_hole_patterns(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        for kind in mounts.MOUNT_NAMES:
            shape = mounts.mount_shape(kind)
            for centre in mounts.COMMON_DEVICE_HOLE_CENTRES:
                check = mounting_pad_check(
                    shape,
                    centre,
                    bottom=mounts.DECK_BOTTOM_Z,
                    thickness=mounts.DECK_THICKNESS,
                    hole_diameter=mounts.MOUNT_HOLE_DIAMETER,
                    pad_diameter=mounts.MOUNT_PAD_DIAMETER,
                )
                self.assertTrue(check["passed"], check)
        for actual, expected in zip(
            mounts.PAS_HOLE_CENTRES, interfaces.PAS_HOLE_CENTRES
        ):
            self.assertAlmostEqual(
                actual[0] - mounts.NAVIGATION_CENTRE_XY[0], expected[0]
            )
            self.assertAlmostEqual(
                actual[1] - mounts.NAVIGATION_CENTRE_XY[1], expected[1]
            )

    def test_expansion_rows_have_ten_mm_pitch_without_an_industry_standard_claim(self):
        from gondola.parts import equipment_mounts as mounts

        rows = mounts.expansion_hole_rows()
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            {row["centre_xy_mm"] for row in rows},
            {(x, y) for x in (-23.0, 23.0) for y in (-10.0, 0.0, 10.0)},
        )
        contract = mounts.expansion_contract()
        self.assertFalse(contract["industry_standard_claimed"])
        self.assertEqual(contract["within_row_pitch_mm"], 10.0)
        self.assertEqual(contract["row_spacing_mm"], 46.0)

    def test_unused_device_or_expansion_hole_blockage_and_missing_land_fail_audit(self):
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import carrier_bore_checks

        original = mounts.mount_shape("battery")
        report = carrier_bore_checks(original)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["physical_plate_hole_count"], 20)
        for centre in (mounts.PAS_HOLE_CENTRES[0], mounts.EXPANSION_HOLE_CENTRES[0]):
            with self.subTest(centre=centre):
                obstruction = Part.makeCylinder(
                    0.4,
                    mounts.DECK_THICKNESS,
                    App.Vector(*centre, mounts.DECK_BOTTOM_Z),
                )
                self.assertFalse(
                    carrier_bore_checks(original.fuse(obstruction))["passed"]
                )
                notch = Part.makeCylinder(
                    0.2,
                    mounts.DECK_THICKNESS,
                    App.Vector(centre[0] + 2, centre[1], mounts.DECK_BOTTOM_Z),
                )
                self.assertFalse(carrier_bore_checks(original.cut(notch))["passed"])


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

    def test_print_metadata_uses_one_sku_without_claiming_half_turn_symmetry(self):
        from gondola.parts import equipment_mounts as mounts

        for kind, name in mounts.MOUNT_NAMES.items():
            obj = self.doc.getObject(name)
            self.assertEqual(obj.PrintSKU, "UniversalEquipmentCarrier")
            self.assertEqual(obj.MountKind, kind)
            self.assertFalse(obj.HalfTurnSymmetric)
            contract = json.loads(obj.MountContract)
            self.assertEqual(len(contract["physical_device_hole_centres_xy_mm"]), 6)
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
            [(x, y, mounts.DECK_BOTTOM_Z) for x, y in centres],
        )
        for name, expected in (
            ("ModuleFCEnvelope", mounts.FC_HOLE_CENTRES),
            (
                "ModulePASEnvelope",
                mounts.PAS_HOLE_CENTRES,
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


if __name__ == "__main__":
    unittest.main()
