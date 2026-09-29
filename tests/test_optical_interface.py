"""Common rail geometry and independently movable optical mounting."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class OpticalRailInterfaceTests(unittest.TestCase):
    def test_proxies_enclose_base_without_filling_channel(self):
        from gondola.parts import optical_interface, optical_mount

        shape = optical_mount.base_shape()
        proxies = Part.makeCompound(
            [s for _, s in optical_interface.base_component_proxies()]
        )
        self.assertLess(abs(shape.cut(proxies).Volume), 1e-5)
        self.assertEqual(len(optical_interface.base_component_proxies()), 3)

    def test_stations_fit_complete_shoe_on_solid_land(self):
        from gondola.parts import optical_interface, rail

        for station in (
            optical_interface.DEFAULT_STATION_X,
            optical_interface.DIRECT_POWER_STATION_X,
        ):
            self.assertLessEqual(abs(station) + rail.SHOE_LENGTH / 2, rail.LENGTH / 2)
            self.assertLessEqual(
                abs(station - round(station / rail.LAND_PITCH) * rail.LAND_PITCH), 4
            )
            pose = optical_interface.placement(station)
            self.assertAlmostEqual(pose.Base.x, station)
            self.assertAlmostEqual(pose.Base.y, rail.CLAMP_SHIFT_Y)

    def test_shoe_does_not_intrude_rail_in_either_clamp_direction(self):
        from gondola.parts import optical_mount, rail

        shape = optical_mount.base_shape()
        track = rail.rail_shape(48, (0,))
        for sign in (-1, 1):
            placed = shape.copy()
            placed.translate(App.Vector(0, sign * rail.CLAMP_SHIFT_Y, 0))
            self.assertLess(abs(placed.common(track).Volume), 1e-5)
