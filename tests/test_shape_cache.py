"""Public shape factories must not expose their mutable cached templates."""

import math
import unittest
from unittest.mock import patch

try:
    import FreeCAD as App
except ImportError:
    App = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ShapeCacheTests(unittest.TestCase):
    def assert_same_shape(self, actual, expected):
        self.assertTrue(actual.isValid())
        self.assertEqual(len(actual.Solids), 1)
        self.assertTrue(actual.Placement.isSame(expected.Placement, 1e-9))
        self.assertLess(abs(actual.cut(expected).Volume), 1e-7)
        self.assertLess(abs(expected.cut(actual).Volume), 1e-7)

    def test_mutating_or_clearing_a_result_preserves_peers_and_later_calls(self):
        from gondola.parts import equipment_mounts, power_mount, purchased_hardware

        factories = (
            (purchased_hardware.screw_shape, ()),
            (purchased_hardware.servo_screw_shape, ()),
            (purchased_hardware.servo_nut_shape, ()),
            (purchased_hardware.hex_nut_shape, ()),
            *(
                (equipment_mounts.mount_shape, (kind,))
                for kind in equipment_mounts.MOUNT_NAMES
            ),
            (power_mount.platform_shape, ()),
        )
        for factory, args in factories:
            with self.subTest(factory=factory.__name__, args=args):
                expected = factory(*args).copy()
                first, peer = factory(*args), factory(*args)
                self.assertIsNot(first, peer)
                first.scale(1.25)
                first.rotate(App.Vector(), App.Vector(1, 2, 3), 37)
                first.translate(App.Vector(100, 200, 300))
                self.assertGreater(abs(first.Volume - expected.Volume), 1)
                self.assert_same_shape(peer, expected)
                self.assert_same_shape(factory(*args), expected)
                first.nullify()
                self.assertTrue(first.isNull())
                self.assert_same_shape(peer, expected)
                self.assert_same_shape(factory(*args), expected)

    def test_screw_length_variants_keep_distinct_geometry_and_owned_results(self):
        from gondola.parts import purchased_hardware

        for factory, radius in (
            (purchased_hardware.screw_shape, 1.0),
            (purchased_hardware.servo_screw_shape, 0.8),
        ):
            with self.subTest(factory=factory.__name__):
                short, long = factory(6), factory(length=8)
                short_reference, long_reference = short.copy(), long.copy()
                self.assertAlmostEqual(
                    long.Volume - short.Volume, math.pi * radius**2 * 2
                )
                self.assertAlmostEqual(short.BoundBox.ZMax, 6)
                self.assertAlmostEqual(long.BoundBox.ZMax, 8)
                short.scale(2)
                long.nullify()
                self.assert_same_shape(factory(length=6), short_reference)
                self.assert_same_shape(factory(8), long_reference)

    def test_fixed_carrier_roles_share_one_template_but_not_mutable_results(self):
        from gondola.parts import equipment_mounts

        equipment_mounts._common_mount_shape.cache_clear()
        self.addCleanup(equipment_mounts._common_mount_shape.cache_clear)
        with patch.object(
            equipment_mounts.mounting_plate,
            "shape",
            wraps=equipment_mounts.mounting_plate.shape,
        ) as plate_builder:
            shapes = [
                equipment_mounts.mount_shape(kind) for kind in ("battery", "accessory")
            ]
            self.assertEqual(plate_builder.call_count, 1)
        self.assertEqual(len({id(shape) for shape in shapes}), 2)
        self.assert_same_shape(shapes[1], shapes[0])
        # Electronics uses the common plate pattern with a rotating lug, not
        # the fixed carrier's integral rail shoe. Its ownership is checked by
        # the mutation-isolation test alongside every other public factory.
        electronics = equipment_mounts.mount_shape("electronics")
        self.assertGreater(
            abs(electronics.cut(shapes[0]).Volume)
            + abs(shapes[0].cut(electronics).Volume),
            1.0,
        )

    def test_invalid_carrier_role_is_rejected_before_template_lookup(self):
        from gondola.parts import equipment_mounts

        with patch.object(equipment_mounts, "_common_mount_shape") as template:
            for kind in ("unknown", "", None):
                with (
                    self.subTest(kind=kind),
                    self.assertRaisesRegex(ValueError, "Unknown equipment mount kind"),
                ):
                    equipment_mounts.mount_shape(kind)
            template.assert_not_called()


if __name__ == "__main__":
    unittest.main()
