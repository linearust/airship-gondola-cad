"""Compact FC carrier, plain accessory carrier and native mounting axes."""

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

    def test_fc_carrier_is_compact_and_has_no_radio_or_navigation_tail(self):
        from gondola.parts import equipment_mounts as mounts

        shape = mounts.mount_shape("electronics")
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        self.assertLessEqual(shape.BoundBox.XLength, 66)
        self.assertLessEqual(shape.BoundBox.YLength, 66)
        for origin, size in (
            ((35, -20, 0), (90, 40, 20)),
            ((-15, 35, 0), (30, 40, 20)),
        ):
            region = Part.makeBox(*size, App.Vector(*origin))
            self.assertLess(abs(shape.common(region).Volume), 1e-6)
        self.assertEqual(
            mounts.mount_hole_centres("electronics"), mounts.FC_HOLE_CENTRES
        )

    def test_accessory_is_plain_full_plate_with_only_confirmed_pas_holes(self):
        from gondola.parts import equipment_mounts as mounts

        x, y = mounts.ACCESSORY_DECK_CENTRE_XY
        width, length = mounts.ACCESSORY_DECK_SIZE
        plate = Part.makeBox(
            width,
            length,
            mounts.DECK_THICKNESS,
            App.Vector(x - width / 2, y - length / 2, mounts.DECK_BOTTOM_Z),
        )
        for hx, hy in mounts.PAS_HOLE_CENTRES:
            plate = plate.cut(
                Part.makeCylinder(
                    mounts.MOUNT_HOLE_DIAMETER / 2,
                    mounts.DECK_THICKNESS + 2,
                    App.Vector(hx, hy, mounts.DECK_BOTTOM_Z - 1),
                )
            )
        shape = mounts.mount_shape("accessory")
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        self.assertLess(abs(plate.cut(shape).Volume), 1e-6)
        self.assertEqual(
            mounts.mount_hole_centres("accessory"), mounts.PAS_HOLE_CENTRES
        )
        self.assertIsNone(mounts.mount_contract("accessory")["stack_interface"])

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

    def test_separate_carriers_preserve_fc_and_published_pas_hole_patterns(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.parts import equipment_mounts as mounts
        from gondola.validation.equipment import mounting_pad_check

        for kind in ("electronics", "accessory"):
            shape = mounts.mount_shape(kind)
            for centre in mounts.mount_hole_centres(kind):
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
        build_mount(self.doc, groups["ElectronicsEquipmentModule"], "electronics")
        build_mount(self.doc, groups["AccessoryEquipmentModule"], "accessory")
        build_equipment(
            self.doc,
            groups["BatteryEquipmentModule"],
            groups["ElectronicsEquipmentModule"],
            groups["AccessoryEquipmentModule"],
        )
        self.doc.recompute()

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
