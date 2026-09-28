"""Purchased alternatives share one support without reusing connector directions."""

import math
import unittest

from gondola.contracts.optical_sensors import SENSOR_PROFILES, get_sensor_profile

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


class OpticalProfileTests(unittest.TestCase):
    def test_selected_equipment_counts_exactly_one_sensor_and_its_mass(self):
        from gondola.contracts.design import SELECTED_EQUIPMENT

        rows = [item for item in SELECTED_EQUIPMENT if "MTF-" in item.model]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].quantity, 1)
        self.assertEqual(rows[0].model, "MicoAir " + get_sensor_profile().model)
        self.assertEqual(rows[0].listed_unit_mass_g, get_sensor_profile().mass_g)

    def test_unknown_model_is_rejected(self):
        for key in ("MTF01", "MTF02", "both", "", []):
            with self.subTest(key=key), self.assertRaises(ValueError):
                get_sensor_profile(key)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OpticalProfileGeometryTests(unittest.TestCase):
    def test_whole_edge_lane_follows_each_distinct_connector_edge(self):
        from gondola.parts import optical_sensor as sensor

        for key, profile in SENSOR_PROFILES.items():
            with self.subTest(model=key):
                body = sensor.envelope_shape(profile)
                lane = sensor.connector_reserve_shape(profile)
                self.assertTrue(lane.isValid())
                self.assertLess(abs(lane.common(body).Volume), 1e-7)
                self.assertAlmostEqual(lane.distToShape(body)[0], 0)
                bb, cb = body.BoundBox, lane.BoundBox
                if key == "MTF01P":
                    self.assertAlmostEqual(cb.YMin, bb.YMax)
                    self.assertAlmostEqual(cb.XLength, bb.XLength)
                    self.assertAlmostEqual(cb.YLength, 12)
                else:
                    self.assertAlmostEqual(cb.XMin, bb.XMax)
                    self.assertAlmostEqual(cb.YLength, bb.YLength)
                    self.assertAlmostEqual(cb.XLength, 12)

    def test_optical_screen_encloses_lower_apertures_and_body(self):
        from gondola.parts import optical_sensor as sensor

        for key, profile in SENSOR_PROFILES.items():
            with self.subTest(model=key):
                body = sensor.envelope_shape(profile)
                screen = sensor.optical_reserve_shape(profile)
                self.assertTrue(screen.isValid())
                self.assertLess(abs(body.cut(screen).Volume), 1e-6)
                self.assertAlmostEqual(screen.BoundBox.ZMin, body.BoundBox.ZMin)
                # A low, outboard ray must not be missed by starting at the
                # taller range tube. It is beyond the case but within42deg.
                point = App.Vector(
                    profile.size_mm[0] / 2 + 0.3, 0, sensor.SENSOR_BOTTOM_Z + 1
                )
                self.assertTrue(screen.isInside(point, 1e-7, True))

    def test_continuous_external_cone_contains_both_fields_and_registration(self):
        from gondola.parts import optical_interface, optical_mount, optical_sensor
        from gondola.validation.optical import _external_field_bound

        doc = App.newDocument("OpticalFullFieldBound")
        try:
            group = doc.addObject("App::Part", "OpticalFlowModule")
            for profile in SENSOR_PROFILES.values():
                bound, _ = _external_field_bound(group, profile)
                for pitch in (-20, -11, 0, 13, 20):
                    rotation = App.Rotation(App.Vector(0, 1, 0), pitch)
                    for distance in (0, 100, 400):
                        expansion = distance * math.tan(
                            math.radians(profile.flow_fov_deg / 2)
                        )
                        for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                            start = App.Vector(
                                sx * (profile.size_mm[0] / 2 + expansion),
                                sy * (profile.size_mm[1] / 2 + expansion),
                                optical_sensor.SENSOR_BOTTOM_Z
                                + profile.optical_origin_min_z_mm
                                + distance,
                            )
                            point = rotation.multVec(start) + App.Vector(
                                *optical_mount.PIVOT_CENTRE
                            )
                            for yaw in (
                                -optical_interface.MAX_REGISTRATION_YAW_RAD,
                                0,
                                optical_interface.MAX_REGISTRATION_YAW_RAD,
                            ):
                                registered = App.Rotation(
                                    App.Vector(0, 0, 1), math.degrees(yaw)
                                ).multVec(point)
                                for tx, ty in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                                    shifted = registered + App.Vector(
                                        tx * optical_interface.MAX_REGISTRATION_X,
                                        ty * optical_interface.MAX_REGISTRATION_Y,
                                        0,
                                    )
                                    self.assertTrue(
                                        bound.isInside(shifted, 1e-7, True),
                                        (
                                            profile.key,
                                            pitch,
                                            distance,
                                            sx,
                                            sy,
                                            yaw,
                                            tx,
                                            ty,
                                        ),
                                    )
        finally:
            App.closeDocument(doc.Name)
