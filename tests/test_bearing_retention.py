"""Native regressions for inward-open bearing cups and the stock spacer stack."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class CaplessBearingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.p = propulsion
        cls.frame = propulsion.fixed_frame_shape()
        cls.carrier = propulsion.moving_carrier_shape()

    def test_full_post_bore_and_outer_shoulder_survive_inward_bearing_float(self):
        """The post must not refill the reversed cup's inboard guide opening."""
        from gondola.cad import translated_shape

        p = self.p
        for pod_y in (-p.PIVOT_HALF_SPAN, p.PIVOT_HALF_SPAN):
            for side in (-1, 1):
                for inward in (0.0, 1.0):
                    start = min(side * (28 - inward), side * (30.5 - inward))
                    bearing = translated_shape(
                        p.bearing_shape(), y=pod_y + start, z=p.PIVOT_Z
                    )
                    self.assertLess(self.frame.common(bearing).Volume, 1e-7)
                    # A full 360-degree outer wall remains along the whole race.
                    wall = p.cylinder(3.2, 2.5, (0, pod_y + start, p.PIVOT_Z)).cut(
                        p.cylinder(3.01, 2.5, (0, pod_y + start, p.PIVOT_Z))
                    )
                    self.assertLess(wall.cut(self.frame).Volume, 1e-7)
                shoulder_y = pod_y + (30.5 if side > 0 else -32)
                shoulder = p.cylinder(4, 1.5, (0, shoulder_y, p.PIVOT_Z)).cut(
                    p.cylinder(3, 1.5, (0, shoulder_y, p.PIVOT_Z))
                )
                self.assertLess(shoulder.cut(self.frame).Volume, 1e-7)

    def test_stock_spacer_profile_keeps_its_large_flange_off_bearing_face(self):
        from gondola.cad import translated_shape

        p = self.p
        spacer = p.bearing_spacer_shape()
        self.assertTrue(spacer.isValid())
        self.assertEqual(len(spacer.Solids), 1)
        # Axially shift the bush to first touch the nominal bearing inner ring.
        seated = translated_shape(spacer, y=0.5)
        annular_shield_region = p.cylinder(3, 0.2, (0, 27.9, 0)).cut(
            p.cylinder(1.85, 0.2, (0, 27.9, 0))
        )
        self.assertLess(seated.common(annular_shield_region).Volume, 1e-7)
        flange = p.cylinder(2.49, 0.99, (0, 26.005, 0)).cut(
            p.cylinder(1.51, 0.99, (0, 26.005, 0))
        )
        self.assertLess(flange.cut(spacer).Volume, 1e-7)
        self.assertAlmostEqual(spacer.BoundBox.YLength, 1.5)

    def test_broad_stop_contact_is_preserved_around_the_output_axis(self):
        p = self.p
        for side in (-1, 1):
            witness = p.cylinder(3.55, 0.01, (0, side * 26 - 0.005, 0)).cut(
                p.cylinder(3.25, 0.01, (0, side * 26 - 0.005, 0))
            )
            contact_volumes = []
            for angle in range(0, 360, 30):
                rotated = self.carrier.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                contact_volumes.append(rotated.common(witness).Volume)
            # Old R3.1 clamp would retain only a fragile 0.1 mm contact rim.
            self.assertGreater(min(contact_volumes), 0.015)
            self.assertLess(max(contact_volumes) - min(contact_volumes), 1e-7)


if __name__ == "__main__":
    unittest.main()
