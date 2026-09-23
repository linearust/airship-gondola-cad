"""Machining blank, prepared example and removable supplied-horn centring aid."""

import unittest

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires FreeCAD")
class ServoCouplingTests(unittest.TestCase):
    @staticmethod
    def _servo_envelope():
        from gondola.cad import box

        case = box(20, 16.6, 7, (-5, -16.8, -3.5))
        ears = box(28, 1, 7, (-9, -4.9, -3.5))
        shape = case.fuse(ears)
        shape.rotate(App.Vector(), App.Vector(0, 1, 0), 90)
        return shape

    @staticmethod
    def _clamp_hardware():
        from gondola.parts import purchased_hardware as hardware
        from gondola.parts import servo_coupling as coupling

        result = []
        for anchors in coupling.fastener_positions():
            rotation = App.Rotation(
                App.Vector(0, 0, 1), App.Vector(*coupling.BOLT_DIRECTION)
            )
            for shape, anchor in (
                (hardware.servo_screw_shape(), anchors["screw"]),
                (hardware.servo_nut_shape(), anchors["nut"]),
            ):
                placed = shape.copy()
                placed.Placement = App.Placement(App.Vector(*anchor), rotation)
                result.append(placed)
        return result

    @staticmethod
    def _shaft_clamp_hardware():
        from gondola.parts import purchased_hardware as hardware
        from gondola.parts import servo_coupling as coupling

        anchors = coupling.shaft_fastener_positions()
        rotation = App.Rotation(App.Vector(0, 0, 1), App.Vector(*anchors["direction"]))
        result = []
        for shape, anchor in (
            (hardware.screw_shape(anchors["length"]), anchors["screw"]),
            (hardware.hex_nut_shape(), anchors["nut"]),
        ):
            placed = shape.copy()
            placed.Placement = App.Placement(App.Vector(*anchor), rotation)
            result.append(placed)
        return result

    @staticmethod
    def _driver_gear():
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts import servo_coupling as coupling

        specification = SELECTED_DRIVE.driver
        axis = App.Vector(0, 1, 0)
        start = coupling.GEAR_START_Y
        shape = Part.makeCylinder(
            specification.hub_diameter_mm / 2,
            specification.hub_extension_mm,
            App.Vector(0, start, 0),
            axis,
        ).fuse(
            Part.makeCylinder(
                specification.outside_diameter_mm / 2,
                specification.face_width_mm,
                App.Vector(0, start + specification.hub_extension_mm, 0),
                axis,
            )
        )
        return shape.cut(
            Part.makeCylinder(
                specification.bore_mm / 2,
                specification.total_length_mm + 0.2,
                App.Vector(0, start - 0.1, 0),
                axis,
            )
        )

    def test_prepared_example_two_joints_and_metal_transmission_fit(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts import servo_coupling as c

        self.assertEqual(SELECTED_DRIVE.driver.bore_mm, c.GEAR_BORE_DIAMETER)
        self.assertEqual(SELECTED_DRIVE.driver.total_length_mm, c.GEAR_LENGTH)
        main, horn, shaft, gear = (
            c.adapter_shape(),
            c.horn_shape(),
            c.driver_shaft_shape(),
            self._driver_gear(),
        )
        fasteners = self._clamp_hardware()
        radial_screw, radial_nut = self._shaft_clamp_hardware()
        shapes = [main, horn, shaft, gear, *fasteners, radial_screw, radial_nut]
        for shape in shapes:
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
        for index, first in enumerate(shapes):
            for second in shapes[index + 1 :]:
                self.assertLess(first.common(second).Volume, 1e-7)
        for a, b in (
            (main, gear),
            (shaft, gear),
            (shaft, radial_screw),
            (main, radial_nut),
            (main, horn),
        ):
            self.assertAlmostEqual(a.distToShape(b)[0], 0, places=6)
        for screw, nut in (fasteners[:2], fasteners[2:]):
            self.assertAlmostEqual(screw.distToShape(horn)[0], 0, places=6)
            self.assertAlmostEqual(nut.distToShape(main)[0], 0, places=6)
            self.assertAlmostEqual(
                screw.BoundBox.YMax - nut.BoundBox.YMax, 1.5, places=6
            )
        head = radial_screw.common(
            c.shaft_frame_shape(
                Part.makeBox(3, 5, 5, App.Vector(-10, c.SHAFT_CLAMP_Y - 2.5, -2.5))
            )
        )
        self.assertGreater(head.Volume, 1)
        self.assertAlmostEqual(head.distToShape(main)[0], 0.5, places=6)
        self.assertGreater(head.distToShape(gear)[0], 1.5)

    def test_blank_has_stock_at_both_holes_and_preparation_only_removes_material(self):
        from gondola.parts import servo_coupling as c

        blank, main, horn = c.adapter_blank_shape(), c.adapter_shape(), c.horn_shape()
        self.assertLess(main.cut(blank).Volume, 1e-7)
        self.assertGreater(blank.cut(main).Volume, 100)
        for (x, z), diameter in zip(c.HORN_BOLT_CENTRES, c.HORN_ADAPTER_HOLE_DIAMETERS):
            passage = Part.makeCylinder(
                diameter / 2,
                c.PLATE_FRONT_Y - c.HORN_BLADE_BOTTOM,
                App.Vector(x, c.HORN_BLADE_BOTTOM, z),
                App.Vector(0, 1, 0),
            )
            self.assertLess(main.common(passage).Volume, 1e-7)
            self.assertLess(horn.common(passage).Volume, 1e-7)
            self.assertGreater(blank.common(passage).Volume, 1)
            edge = Part.makeCylinder(
                diameter / 2 + 0.01,
                c.PLATE_FRONT_Y - c.HORN_HEIGHT,
                App.Vector(x, c.HORN_HEIGHT, z),
                App.Vector(0, 1, 0),
            )
            self.assertGreater(main.common(edge).Volume, 1e-3)
        self.assertEqual(c.HORN_SKU, "KST_X06_SUPPLIED_HORN")
        self.assertEqual(c.HORN_ADAPTER_HOLE_DIAMETERS, (1.7, 1.8))

    def test_close_hole_and_second_fastener_bound_gross_rotation_without_register_claim(
        self,
    ):
        from gondola.parts import servo_coupling as c

        main, horn = c.adapter_shape(), c.horn_shape()
        screws = self._clamp_hardware()[::2]
        self.assertGreaterEqual(
            c.HORN_BOLT_CENTRES[1][0] - c.HORN_BOLT_CENTRES[0][0], 4
        )
        for angle in (-3, 3):
            turned = horn.copy()
            turned.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertLess(turned.common(main).Volume, 1e-7)
            for screw in screws:
                self.assertGreater(turned.common(screw).Volume, 1e-3)
        # The generous hub cavity deliberately supplies no old exact root/tip
        # registration. Actual axis alignment comes from matched preparation.
        moved = horn.copy()
        moved.translate(App.Vector(0.1, 0, 0))
        self.assertLess(moved.common(main).Volume, 1e-7)
        contract = c.machining_contract()
        self.assertFalse(contract["supplied_horn_measured"])
        self.assertTrue(contract["prepared_preview_is_example"])
        self.assertIn("measured M1.6 shank", contract["centering_sequence"])
        self.assertIn("runout", contract["final_alignment"])

    def test_front_nuts_remove_far_first_then_near_without_other_joint_collision(self):
        from gondola.parts import servo_coupling as c

        near_screw, near_nut, far_screw, far_nut = self._clamp_hardware()
        common = [
            c.adapter_shape(),
            c.horn_shape(),
            c.driver_shaft_shape(),
            self._driver_gear(),
            near_screw,
            far_screw,
            *self._shaft_clamp_hardware(),
            self._servo_envelope(),
        ]
        for nut, other in ((far_nut, [near_nut]), (near_nut, [])):
            obstacles = common + other
            for step in range(1, 13):
                released = nut.copy()
                released.translate(App.Vector(0, step * 0.25, 0))
                for obstacle in obstacles:
                    self.assertLess(released.common(obstacle).Volume, 1e-7)
            for step in range(1, 41):
                cleared = released.copy()
                cleared.translate(App.Vector(step * 0.5, 0, 0))
                for obstacle in obstacles:
                    self.assertLess(cleared.common(obstacle).Volume, 1e-7)

    def test_metal_stub_seats_on_perforated_floor_and_key_blocks_rotation(self):
        from gondola.parts import servo_coupling as c

        main, shaft = c.adapter_shape(), c.driver_shaft_shape()
        self.assertAlmostEqual(shaft.BoundBox.YLength, 18, places=6)
        self.assertAlmostEqual(shaft.BoundBox.ZMin, -1, places=6)
        self.assertAlmostEqual(shaft.BoundBox.YMax, c.GEAR_START_Y + 10, places=6)
        displaced = shaft.copy()
        displaced.translate(App.Vector(0, -0.01, 0))
        self.assertGreater(displaced.common(main).Volume, 0.01)
        for angle in (-15, 15):
            displaced = shaft.copy()
            displaced.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertGreater(displaced.common(main).Volume, 1e-3)
        displaced = shaft.copy()
        displaced.translate(App.Vector(0, 0.5, 0))
        self.assertLess(displaced.common(main).Volume, 1e-7)

    def test_radial_nut_and_negative_z_screw_have_open_loading_paths(self):
        from gondola.parts import servo_coupling as c

        main, shaft, gear = (
            c.adapter_shape(),
            c.driver_shaft_shape(),
            self._driver_gear(),
        )
        screw, nut = self._shaft_clamp_hardware()
        for step in range(1, 21):
            lifted = nut.copy()
            lifted.translate(c.shaft_frame_point(0, 0, step * 0.5))
            for obstacle in (main, shaft, gear, *self._clamp_hardware()):
                self.assertLess(lifted.common(obstacle).Volume, 1e-7)
            withdrawn = screw.copy()
            withdrawn.translate(c.shaft_frame_point(-step * 0.5, 0, 0))
            for obstacle in (main, shaft, nut, gear, *self._clamp_hardware()):
                self.assertLess(withdrawn.common(obstacle).Volume, 1e-7)

    def test_rear_heads_clear_servo_through_full_nominal_input_travel(self):
        from gondola.parts import servo_coupling as c

        case = self._servo_envelope()
        for angle in range(-60, 61, 5):
            for shape in (
                c.adapter_shape(),
                c.driver_shaft_shape(),
                *self._clamp_hardware(),
                *self._shaft_clamp_hardware(),
            ):
                rotated = shape.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                self.assertLess(rotated.common(case).Volume, 1e-7)
                self.assertGreaterEqual(rotated.distToShape(case)[0], 0.5 - 1e-7)

    def test_planar_walls_floor_and_jig_guide_remain_open_and_at_least_1_5mm(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.manufacturing import planar_wall_regions

        for main in (c.adapter_blank_shape(), c.adapter_shape()):
            self.assertEqual(
                [
                    r
                    for r in planar_wall_regions(main)
                    if r["material_thickness_mm"] < 1.5 - 1e-6
                ],
                [],
            )
            for x, z in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                section = Part.makeLine(
                    App.Vector(x, c.OEM_HEAD_CAVITY_TOP_Y, z),
                    App.Vector(x, c.SHAFT_START_Y, z),
                )
                self.assertAlmostEqual(main.common(section).Length, 1.5, places=6)
            guide = Part.makeCylinder(
                1.2,
                c.GEAR_START_Y - c.BODY_BACK_Y,
                App.Vector(0, c.BODY_BACK_Y, 0),
                App.Vector(0, 1, 0),
            )
            self.assertLess(main.common(guide).Volume, 1e-7)
        self.assertAlmostEqual(c.SHAFT_NUT_SEAT_X - c.SHAFT_BOSS_END_X, 1.5)

    def test_centred_jig_works_across_declared_synthetic_entry_range(self):
        from gondola.parts import servo_coupling as c

        main, jig = c.adapter_blank_shape(), c.centering_jig_shape()
        self.assertTrue(jig.isValid())
        self.assertEqual(len(jig.Solids), 1)
        for diameter in (0.8, 1.2, 1.6):
            offset = c.JIG_REFERENCE_ENTRY_Y - (
                c.JIG_NOSE_START_Y
                + (diameter - c.JIG_NOSE_TIP_DIAMETER)
                / (c.JIG_NOSE_BASE_DIAMETER - c.JIG_NOSE_TIP_DIAMETER)
                * c.JIG_NOSE_LENGTH
            )
            placed = jig.copy()
            placed.translate(App.Vector(0, offset, 0))
            self.assertLess(main.common(placed).Volume, 1e-7)
            # If the finished guide is moved off-axis the actual socket stops
            # it. This is nominal tool guidance, not print accuracy proof.
            displaced = placed.copy()
            displaced.translate(App.Vector(0.11, 0, 0))
            self.assertGreater(main.common(displaced).Volume, 0.01)
        self.assertIn("prototype", c.metrics()["qualification"].lower())

    def test_oem_head_envelope_clears_but_unknown_original_screw_requires_adapter_removal(
        self,
    ):
        from gondola.parts import servo_coupling as c

        main = c.adapter_shape()
        head = Part.makeCylinder(2.2, 1.9, App.Vector(0, 3.5, 0), App.Vector(0, 1, 0))
        self.assertLess(main.common(head).Volume, 1e-7)
        self.assertAlmostEqual(main.distToShape(head)[0], 0.2, places=6)
        self.assertIn(
            "Remove gear, metal stub and adapter",
            c.machining_contract()["centre_screw_service"],
        )


@unittest.skipIf(App is None, "Requires FreeCAD")
class InputShaftEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("InputShaftEvidenceRegression")
        cls.module = propulsion.build_propulsion_module(cls.doc)
        propulsion.build_fit_coupons(cls.doc)
        cls.doc.recompute()

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_both_mirrored_drives_retain_the_shaft_through_bounded_travel(self):
        from gondola.validation.propulsion import direct_adapter_fit_check

        for prefix in ("Port", "Starboard"):
            pod = self.doc.getObject(prefix + "Pod")
            original = float(pod.Tilt)
            try:
                for angle in (-180, 0, 180):
                    pod.Tilt = angle
                    self.doc.recompute()
                    result = direct_adapter_fit_check(self.doc, prefix)
                    self.assertTrue(result["passed"], result)
                    self.assertAlmostEqual(result["metal_projection_beyond_gear_mm"], 2)
            finally:
                pod.Tilt = original
                self.doc.recompute()

    def test_full_gear_engagement_does_not_hide_a_missing_end_reserve(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.propulsion import direct_adapter_fit_check

        shaft = self.doc.PortInputShaft
        original = shaft.Shape.copy()
        try:
            # Keep the entire socket and selected gear journal, but remove the
            # two-millimetre projection beyond the gear's front face.
            shaft.Shape = original.cut(
                Part.makeBox(
                    6,
                    3,
                    6,
                    App.Vector(
                        -3,
                        coupling.HORN_BOTTOM_Y + coupling.GEAR_START_Y + 8,
                        -3,
                    ),
                )
            )
            self.doc.recompute()
            result = direct_adapter_fit_check(self.doc, "Port")
            self.assertLess(result["missing_metal_gear_engagement_mm3"], 1e-5)
            self.assertGreater(result["missing_gear_end_reserve_mm3"], 1)
            self.assertFalse(result["passed"], result)
        finally:
            shaft.Shape = original
            self.doc.recompute()

    def test_unseated_input_stub_is_rejected(self):
        from gondola.validation.propulsion import input_shaft_retention_check

        shaft = self.doc.PortInputShaft
        original = App.Placement(shaft.Placement)
        try:
            shaft.Placement.Base += App.Vector(0, 0.3, 0)
            self.doc.recompute()
            result = input_shaft_retention_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(result["missing_nominal_stub_mm3"], 1)
            self.assertLess(result["shaft_stop_contact_mm2"], 1e-7)
        finally:
            shaft.Placement = original
            self.doc.recompute()

    def test_radial_screw_must_reach_the_flat_and_keep_its_head_free(self):
        from gondola.validation.propulsion import input_shaft_retention_check

        screw = self.doc.PortInputShaftClampBolt
        original = App.Placement(screw.Placement)
        try:
            screw.Placement.Base += App.Vector(0, 0, -0.3)
            self.doc.recompute()
            result = input_shaft_retention_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertLess(result["screw_tip_to_flat_contact_mm2"], 1e-7)
        finally:
            screw.Placement = original
            self.doc.recompute()

    def test_nut_must_bear_on_its_retaining_wall(self):
        from gondola.validation.propulsion import input_shaft_retention_check

        nut = self.doc.PortInputShaftClampNut
        original = App.Placement(nut.Placement)
        try:
            for displacement in (-0.1, -0.2):
                nut.Placement = App.Placement(original)
                nut.Placement.Base += App.Vector(0, 0, displacement)
                self.doc.recompute()
                result = input_shaft_retention_check(self.doc, "Port")
                self.assertFalse(result["passed"], result)
                self.assertLess(result["nut_to_retaining_wall_contact_mm2"], 1e-7)
        finally:
            nut.Placement = original
            self.doc.recompute()

    def test_oversized_pocket_rejects_a_freely_rotating_minimum_nut(self):
        from gondola.parts import purchased_hardware as hardware
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.propulsion import input_shaft_retention_check

        adapter = self.doc.PortHornGearAdapter
        original = adapter.Shape.copy()
        try:
            enlarged = hardware.hex_prism(4.5, coupling.SHAFT_NUT_POCKET_LENGTH)
            enlarged.Placement = App.Placement(
                App.Vector(
                    coupling.SHAFT_NUT_SEAT_X,
                    coupling.HORN_BOTTOM_Y + coupling.SHAFT_CLAMP_Y,
                    0,
                ),
                App.Rotation(
                    App.Vector(0, 0, 1), App.Vector(*coupling.SHAFT_BOLT_DIRECTION)
                ),
            )
            # Preserve the nut's axial reaction wall, shaft stop and screw
            # contact. Only the pocket's rotation-blocking sides are enlarged.
            adapter.Shape = original.cut(
                coupling.shaft_frame_shape(enlarged)
            ).removeSplitter()
            self.doc.recompute()
            result = input_shaft_retention_check(self.doc, "Port")
            capture = result["minimum_nut_capture"]
            self.assertGreater(result["nut_to_retaining_wall_contact_mm2"], 1)
            self.assertGreater(result["screw_tip_to_flat_contact_mm2"], 1)
            self.assertGreater(result["shaft_stop_contact_mm2"], 1)
            self.assertLess(capture["neutral_pocket_overlap_mm3"], 1e-7)
            self.assertGreater(capture["retaining_wall_contact_mm2"], 1)
            self.assertTrue(
                all(
                    row["pocket_probe_penetration_mm3"] < 1e-7
                    for row in capture["rotation_stop_checks"]
                )
            )
            self.assertFalse(capture["passed"], capture)
            self.assertFalse(result["passed"], result)
        finally:
            adapter.Shape = original
            self.doc.recompute()

    def test_adapter_continuous_service_preserves_the_retained_horn_socket(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.validation.propulsion import adapter_service_check
        from gondola.validation.propulsion_service import module_service_shapes

        shapes, missing = module_service_shapes(self.doc, self.module)
        self.assertFalse(missing)
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            result = adapter_service_check(
                shapes[prefix + "HornGearAdapter"],
                [(0, 0, 0), (0, sign * 1.5, 0), (sign * 40, sign * 1.5, 0)],
                {suffix: shapes[prefix + suffix] for suffix in ("ServoHorn", "Servo")},
                SELECTED_DRIVE,
                sign,
            )
            self.assertTrue(result["passed"], result)
            self.assertLess(result["adapter_outside_reference_envelope_mm3"], 1e-7)
            self.assertIn("face-prism", result["segments"][0]["method"])

    def test_adapter_service_rejects_geometry_outside_its_conservative_reference(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.validation.propulsion import adapter_service_check
        from gondola.validation.propulsion_service import module_service_shapes

        shapes, _ = module_service_shapes(self.doc, self.module)
        shape = shapes["PortHornGearAdapter"]
        bounds = shape.BoundBox
        tab = Part.makeBox(
            1.5,
            1,
            1,
            App.Vector(
                bounds.XMax - 0.5, bounds.YMin + 0.5, SELECTED_DRIVE.input_z_mm - 0.5
            ),
        )
        altered = shape.fuse(tab).removeSplitter()
        self.assertTrue(altered.isValid())
        self.assertEqual(len(altered.Solids), 1)
        result = adapter_service_check(
            altered, [(0, 0, 0), (0, 1.5, 0), (40, 1.5, 0)], {}, SELECTED_DRIVE, 1
        )
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["adapter_outside_reference_envelope_mm3"], 0.9)

    def test_adapter_service_detects_a_real_obstacle_between_clear_waypoints(self):
        from gondola.cad import translated_shape
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.propulsion import adapter_service_check
        from gondola.validation.propulsion_service import module_service_shapes

        shapes, _ = module_service_shapes(self.doc, self.module)
        shape = shapes["PortHornGearAdapter"]
        waypoints = [(0, 0, 0), (0, 1.5, 0), (40, 1.5, 0)]
        obstacle = Part.makeBox(
            0.1,
            0.2,
            0.2,
            App.Vector(
                SELECTED_DRIVE.input_x_mm + 30,
                coupling.HORN_BOTTOM_Y + coupling.BODY_BACK_Y + 3.5,
                SELECTED_DRIVE.input_z_mm - 0.1,
            ),
        )
        for displacement in waypoints:
            endpoint = translated_shape(shape, *displacement)
            self.assertLess(endpoint.common(obstacle).Volume, 1e-7)
        midpoint = translated_shape(shape, 20, 1.5, 0)
        self.assertGreater(midpoint.common(obstacle).Volume, 0.003)
        result = adapter_service_check(
            shape, waypoints, {"thin_obstacle": obstacle}, SELECTED_DRIVE, 1
        )
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any(
                row["intersection_mm3"]["thin_obstacle"] > 0.003
                for row in result["segments"]
            )
        )


if __name__ == "__main__":
    unittest.main()
