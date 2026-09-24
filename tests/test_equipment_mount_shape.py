"""Shared FC/P-AS support and consistent native equipment mounting axes."""

import json
import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class EquipmentMountShapeTests(unittest.TestCase):
    def test_navigation_spine_clears_rail_in_both_clamped_lateral_poses(self):
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts import equipment_mounts as mounts
        from gondola.parts import rail
        from gondola.validation.geometry import intersection_volume

        station = next(
            s for s in MODULE_STATIONS if s.object_name == "ElectronicsEquipmentModule"
        )
        rail_shape = rail.rail_shape()
        local = mounts.mount_shape("electronics")
        # This section lies above the rail head but outside the mating shoe.
        # Inspect the actual lower surface, not just the unchanged top plane.
        section = local.common(Part.makeBox(10, 20, 8, App.Vector(25, -10, 5)))
        for side in (-1, 1):
            pose = App.Placement(
                App.Vector(station.x_mm, side * rail.CLAMP_SHIFT_Y, 0),
                App.Rotation(App.Vector(0, 0, 1), station.yaw_deg),
            )
            body = local.copy()
            body.Placement = pose.multiply(body.Placement)
            probe = section.copy()
            probe.Placement = pose.multiply(probe.Placement)
            with self.subTest(clamped_side=side):
                self.assertLess(intersection_volume(body, rail_shape), 1e-6)
                self.assertGreaterEqual(probe.distToShape(rail_shape)[0], 0.8 - 1e-6)

    def test_common_x_spine_reaches_fc_and_pas_pads_without_a_second_branch(self):
        from gondola.parts import equipment_mounts as mounts

        shape = mounts.mount_shape("electronics")
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        start, end = mounts.ELECTRONICS_SUPPORT_SPINES[0]
        self.assertEqual(start, mounts.FC_HOLE_CENTRES[0])
        self.assertEqual(end, mounts.GPS_CENTRE_XY)
        self.assertEqual(start[1], 0)
        self.assertEqual({centre[1] for centre in mounts.PAS_HOLE_CENTRES}, {0})
        strip = Part.makeBox(
            end[0] - start[0],
            mounts.ARM_WIDTH,
            mounts.DECK_THICKNESS,
            App.Vector(start[0], -mounts.ARM_WIDTH / 2, mounts.DECK_BOTTOM_Z),
        )
        for x, hole_y in mounts.FC_HOLE_CENTRES + mounts.PAS_HOLE_CENTRES:
            strip = strip.cut(
                Part.makeCylinder(
                    mounts.MOUNT_HOLE_DIAMETER / 2,
                    mounts.DECK_THICKNESS + 2,
                    App.Vector(x, hole_y, mounts.DECK_BOTTOM_Z - 1),
                )
            )
        self.assertLess(abs(strip.cut(shape).Volume), 1e-6)

    def test_gps_adhesive_pad_is_integral_and_not_pierced_by_pas_holes(self):
        from gondola.parts import equipment_mounts as mounts

        pad = Part.makeBox(
            *mounts.GPS_ADHESIVE_SIZE,
            mounts.DECK_THICKNESS,
            App.Vector(
                mounts.GPS_CENTRE_XY[0] - mounts.GPS_ADHESIVE_SIZE[0] / 2,
                mounts.GPS_CENTRE_XY[1] - mounts.GPS_ADHESIVE_SIZE[1] / 2,
                mounts.DECK_BOTTOM_Z,
            ),
        )
        self.assertLess(pad.cut(mounts.mount_shape("electronics")).Volume, 1e-6)

    def test_former_offset_pas_branch_is_absent(self):
        from gondola.parts import equipment_mounts as mounts

        # Outside the shoe and optical tabs, the former Y=-9.3 member ran
        # through this 4 mm band outside the reinforced shared member. Keeping it would duplicate the
        # shared X spine even if all mounting holes were correctly relocated.
        clear = Part.makeBox(
            12, 4, mounts.DECK_THICKNESS, App.Vector(26, -11.8, mounts.DECK_BOTTOM_Z)
        )
        shape = mounts.mount_shape("electronics")
        self.assertLess(abs(shape.common(clear).Volume), 1e-6)

    def test_shared_spine_preserves_full_profile_and_published_pas_pattern(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.parts import equipment_mounts as mounts

        shape = mounts.mount_shape("electronics")
        section = shape.common(
            Part.makeBox(
                1,
                18,
                5,
                App.Vector(29.5, -9, mounts.DECK_BOTTOM_Z - 2),
            )
        )
        self.assertAlmostEqual(section.Volume, 42, places=6)
        self.assertAlmostEqual(section.BoundBox.YLength, 14, places=6)
        self.assertAlmostEqual(section.BoundBox.ZLength, 3, places=6)
        self.assertAlmostEqual(section.BoundBox.Center.y, 0, places=6)
        self.assertAlmostEqual(section.BoundBox.ZMax, mounts.SUPPORT_FACE_Z, places=6)
        self.assertEqual(
            tuple(
                (x - mounts.PAS_CENTRE_XY[0], y - mounts.PAS_CENTRE_XY[1])
                for x, y in mounts.PAS_HOLE_CENTRES
            ),
            interfaces.PAS_HOLE_CENTRES,
        )
        self.assertEqual(
            mounts.PAS_HOLE_CENTRES[1][0] - mounts.PAS_HOLE_CENTRES[0][0],
            interfaces.PAS_HOLE_PITCH,
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
        build_equipment(
            self.doc,
            groups["BatteryEquipmentModule"],
            groups["ElectronicsEquipmentModule"],
        )
        self.doc.recompute()

    def test_native_hole_axis_metadata_follows_shared_support(self):
        from gondola.contracts import equipment_interfaces as interfaces
        from gondola.parts import equipment_mounts as mounts

        centres = mounts.FC_HOLE_CENTRES + mounts.PAS_HOLE_CENTRES
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
                tuple((54 + x, y + 9.3) for x, y in interfaces.PAS_HOLE_CENTRES),
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
