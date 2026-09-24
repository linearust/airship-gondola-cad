"""Load-path geometry of the straight P-AS support without relocated device axes."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class EquipmentMountShapeTests(unittest.TestCase):
    def test_one_straight_full_thickness_member_reaches_both_pas_holes(self):
        from gondola.parts import equipment_mounts as mounts

        shape = mounts.mount_shape("electronics")
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        x0, y = mounts.PAS_ARM_ROOT_XY
        self.assertEqual(x0, 0)
        self.assertEqual({centre[1] for centre in mounts.PAS_HOLE_CENTRES}, {y})
        strip = Part.makeBox(
            mounts.PAS_HOLE_CENTRES[-1][0] - x0,
            mounts.ARM_WIDTH,
            mounts.DECK_THICKNESS,
            App.Vector(x0, y - mounts.ARM_WIDTH / 2, mounts.DECK_BOTTOM_Z),
        )
        for x, hole_y in mounts.PAS_HOLE_CENTRES:
            strip = strip.cut(
                Part.makeCylinder(
                    mounts.MOUNT_HOLE_DIAMETER / 2,
                    mounts.DECK_THICKNESS + 2,
                    App.Vector(x, hole_y, mounts.DECK_BOTTOM_Z - 1),
                )
            )
        self.assertLess(abs(strip.cut(shape).Volume), 1e-6)

    def test_former_diagonal_elbow_is_open_below_the_fc_edge(self):
        from gondola.parts import equipment_mounts as mounts

        # This rectangle lies between the unchanged FC arm and straight P-AS
        # arm. The former diagonal connection crossed it; an extra diagonal
        # would preserve an unnecessary branch even if a straight arm existed.
        clear = Part.makeBox(
            6, 2, mounts.DECK_THICKNESS, App.Vector(26, -4, mounts.DECK_BOTTOM_Z)
        )
        shape = mounts.mount_shape("electronics")
        self.assertLess(abs(shape.common(clear).Volume), 1e-6)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class FCInstallationTests(unittest.TestCase):
    def setUp(self):
        from gondola.cad import create_group
        from gondola.contracts.design import MODULE_STATIONS
        from gondola.parts.equipment_envelopes import build_equipment

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
        build_equipment(
            self.doc,
            groups["BatteryEquipmentModule"],
            groups["ElectronicsEquipmentModule"],
        )
        self.doc.recompute()

    def test_native_board_pose_preserves_heading_after_carrier_turn(self):
        from gondola.validation.equipment import fc_installation_check

        result = fc_installation_check(self.doc)
        self.assertTrue(result["passed"], result)

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
