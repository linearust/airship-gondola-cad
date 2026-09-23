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


if __name__ == "__main__":
    unittest.main()
