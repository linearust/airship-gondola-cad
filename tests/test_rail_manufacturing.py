"""Critical walls must be real material, including after a local defect."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class RailManufacturingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import equipment_mounts, rail
        from gondola.validation.manufacturing import rail_mount_wall_probes

        cls.shapes = {
            "ContinuousRail": rail.rail_shape(),
            "BatteryMount": equipment_mounts.mount_shape("battery"),
        }
        cls.probes = {probe[0]: probe for probe in rail_mount_wall_probes()}

    def test_sections_match_native_material(self):
        from gondola.validation.manufacturing import material_length_on_line

        for feature, name, start, end, expected in self.probes.values():
            with self.subTest(feature=feature):
                actual = material_length_on_line(self.shapes[name], start, end)
                self.assertAlmostEqual(actual, expected, places=6)
                if feature == "carrier_nut_pocket_bottom_opening":
                    self.assertEqual(expected, 0)
                else:
                    self.assertGreaterEqual(actual, 1.5 - 1e-6)

    def test_raised_lower_legs_preserve_minimum_carrier_wall(self):
        from gondola.validation.manufacturing import planar_wall_regions

        regions = planar_wall_regions(self.shapes["BatteryMount"])
        self.assertTrue(
            all(region["material_thickness_mm"] >= 1.5 - 1e-6 for region in regions)
        )

    def test_local_lower_floor_thinning_is_detected(self):
        from gondola.validation.manufacturing import planar_wall_regions

        # Remove only the inner 0.65 mm of the leg's lowest 0.1 mm. The
        # resulting 1.35 mm axial floor must fail the unchanged 1.5 mm screen.
        floor_notch = Part.makeBox(10, 3.8, 0.1, App.Vector(-5, -1.9, 2.5))
        defective = self.shapes["BatteryMount"].cut(floor_notch)
        regions = planar_wall_regions(defective)
        self.assertTrue(
            any(region["material_thickness_mm"] < 1.5 - 1e-6 for region in regions)
        )

    def test_enlarging_slot_reduces_top_ligament(self):
        from gondola.validation.manufacturing import material_length_on_line

        _, name, start, end, expected = self.probes["rail_slot_top_ligament"]
        cut = Part.makeBox(2, 4, 0.3, App.Vector(-1, -2, 7.6))
        actual = material_length_on_line(self.shapes[name].cut(cut), start, end)
        self.assertAlmostEqual(expected - actual, 0.2, places=6)

    def test_thinned_u_clamp_leg_is_detected(self):
        from gondola.validation.manufacturing import material_length_on_line

        _, name, start, end, expected = self.probes["carrier_clamp_leg"]
        cut = Part.makeBox(2, 0.2, 1, App.Vector(3, -5.25, 7.5))
        actual = material_length_on_line(self.shapes[name].cut(cut), start, end)
        self.assertAlmostEqual(expected - actual, 0.2, places=6)

    def test_both_bearing_floors_and_top_pocket_ligament_are_real_material(self):
        from gondola.validation.manufacturing import material_length_on_line

        cuts = {
            "carrier_nut_pocket_floor": Part.makeBox(
                1, 0.2, 1, App.Vector(2, 1.25, 5.5)
            ),
            "carrier_head_recess_floor": Part.makeBox(
                1, 0.2, 1, App.Vector(2, -3.25, 5.5)
            ),
            "carrier_nut_pocket_top_ligament": Part.makeBox(
                1, 1, 0.2, App.Vector(-0.5, 4.0, 9.6)
            ),
        }
        for feature, cut in cuts.items():
            with self.subTest(feature=feature):
                _, name, start, end, expected = self.probes[feature]
                actual = material_length_on_line(self.shapes[name].cut(cut), start, end)
                self.assertAlmostEqual(expected - actual, 0.2, places=6)

    def test_reintroduced_lower_pocket_lip_is_detected_as_an_obstruction(self):
        from gondola.validation.manufacturing import material_length_on_line

        _, name, start, end, expected = self.probes["carrier_nut_pocket_bottom_opening"]
        lip = Part.makeBox(1, 1, 0.2, App.Vector(-0.5, 4, 3.5))
        actual = material_length_on_line(self.shapes[name].fuse(lip), start, end)
        self.assertEqual(expected, 0)
        self.assertAlmostEqual(actual, 0.2, places=6)


if __name__ == "__main__":
    unittest.main()
