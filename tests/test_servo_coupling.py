"""Factory horn threads, integral registration and unchanged metal shaft retention."""

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
        from gondola.parts import servo_coupling as c

        result = []
        for anchors in c.fastener_positions():
            placed = hardware.servo_screw_shape(c.HORN_CLAMP_LENGTH).copy()
            placed.Placement = App.Placement(
                App.Vector(*anchors["screw"]),
                App.Rotation(App.Vector(0, 0, 1), App.Vector(*c.BOLT_DIRECTION)),
            )
            result.append(placed)
        return result

    @staticmethod
    def _shaft_clamp_hardware():
        from gondola.parts import purchased_hardware as hardware
        from gondola.parts import servo_coupling as c

        anchors = c.shaft_fastener_positions()
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
        from gondola.parts import servo_coupling as c

        spec = SELECTED_DRIVE.driver
        axis = App.Vector(0, 1, 0)
        start = c.GEAR_START_Y
        shape = Part.makeCylinder(
            spec.hub_diameter_mm / 2,
            spec.hub_extension_mm,
            App.Vector(0, start, 0),
            axis,
        ).fuse(
            Part.makeCylinder(
                spec.outside_diameter_mm / 2,
                spec.face_width_mm,
                App.Vector(0, start + spec.hub_extension_mm, 0),
                axis,
            )
        )
        return shape.cut(
            Part.makeCylinder(
                spec.bore_mm / 2,
                spec.total_length_mm + 0.2,
                App.Vector(0, start - 0.1, 0),
                axis,
            )
        )

    def test_selected_horn_and_front_screws_clear_the_metal_transmission(self):
        from gondola.parts import servo_coupling as c

        shapes = [
            c.adapter_shape(),
            c.horn_shape(),
            c.driver_shaft_shape(),
            self._driver_gear(),
            *self._clamp_hardware(),
            *self._shaft_clamp_hardware(),
        ]
        for shape in shapes:
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
        for index, first in enumerate(shapes):
            for second in shapes[index + 1 :]:
                self.assertLess(first.common(second).Volume, 1e-7)
        self.assertEqual(c.HORN_SKU, "ALI_PTK_15T_4MM_HORN")
        self.assertEqual(c.BOLT_DIRECTION, (0, -1, 0))
        for screw in self._clamp_hardware():
            self.assertAlmostEqual(screw.distToShape(c.adapter_shape())[0], 0, places=6)
            self.assertAlmostEqual(c.HORN_HEIGHT - screw.BoundBox.YMin, 1.4, places=6)
            self.assertAlmostEqual(
                screw.BoundBox.YMin - c.HORN_BLADE_BOTTOM, 0.2, places=6
            )

    def test_factory_hole_passages_require_no_horn_drilling(self):
        from gondola.parts import servo_coupling as c

        horn, adapter = c.horn_shape(), c.adapter_shape()
        for x in (6.6, 9.4, 12.2):
            passage = Part.makeCylinder(
                0.8, 1.6, App.Vector(x, c.HORN_BLADE_BOTTOM, 0), App.Vector(0, 1, 0)
            )
            self.assertLess(horn.common(passage).Volume, 1e-7)
        for x, z in c.HORN_BOLT_CENTRES:
            passage = Part.makeCylinder(
                0.8,
                c.FASTENER_SEAT_Y - c.HORN_HEIGHT,
                App.Vector(x, c.HORN_HEIGHT, z),
                App.Vector(0, 1, 0),
            )
            self.assertLess(adapter.common(passage).Volume, 1e-7)
        self.assertTrue(
            all(set(anchors) == {"screw"} for anchors in c.fastener_positions())
        )
        self.assertFalse(hasattr(c, "centering_jig_shape"))

    def test_outer_slot_tolerates_pitch_error_without_tight_head_overlap(self):
        from gondola.parts import servo_coupling as c

        adapter = c.adapter_shape()
        near, far = self._clamp_hardware()
        for shift in (-0.4, 0.4):
            moved = far.copy()
            moved.translate(App.Vector(shift, 0, 0))
            self.assertLess(moved.common(adapter).Volume, 1e-7)
            self.assertLess(moved.common(near).Volume, 1e-7)
        for x, z in ((0.2, 0), (0, -0.2), (0, 0.2)):
            # The adapter moves relative to the fixed horn/screws. Its locating
            # arc blocks displacement while the larger screw passages remain clear.
            moved = adapter.copy()
            moved.translate(App.Vector(x, 0, z))
            self.assertGreater(moved.common(c.horn_shape()).Volume, 1e-4)
            for screw in (near, far):
                self.assertLess(moved.common(screw).Volume, 1e-7)

    def test_minimum_accepted_head_land_has_support_across_the_outer_slot(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import _plane_contact

        adapter = c.adapter_shape()
        for x, z in c.HORN_BOLT_CENTRES:
            allowance = (
                c.HORN_ADAPTER_SLOT_ALLOWANCE
                if x == c.HORN_BOLT_CENTRES[-1][0]
                else 0.0
            )
            for offset in (-allowance, 0.0, allowance):
                land = Part.makeCylinder(
                    c.HORN_MIN_HEAD_BEARING_DIAMETER / 2,
                    0.1,
                    App.Vector(x + offset, c.FASTENER_SEAT_Y, z),
                    App.Vector(0, 1, 0),
                )
                self.assertGreaterEqual(
                    _plane_contact(adapter, land, c.FASTENER_SEAT_Y), 1.0
                )

    def test_short_front_screws_withdraw_after_driver_gear_removal(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.propulsion import _horn_clamp_service_check

        near, far = self._clamp_hardware()
        fixed = {
            "adapter": c.adapter_shape(),
            "horn": c.horn_shape(),
            "shaft": c.driver_shaft_shape(),
            "servo": self._servo_envelope(),
        }
        for name, screw, other in (("Far", far, {"Near": near}), ("Near", near, {})):
            with self.subTest(joint=name):
                result = _horn_clamp_service_check(screw, fixed | other, (0, 1, 0))
                self.assertTrue(result["passed"], result)

    def test_metal_stub_retains_stop_flat_and_gear_end_reserve(self):
        from gondola.parts import servo_coupling as c

        main, shaft = c.adapter_shape(), c.driver_shaft_shape()
        self.assertAlmostEqual(shaft.BoundBox.YLength, 18)
        self.assertAlmostEqual(shaft.BoundBox.ZMin, -1)
        self.assertAlmostEqual(shaft.BoundBox.YMax, c.GEAR_START_Y + 10)
        displaced = shaft.copy()
        displaced.translate(App.Vector(0, -0.01, 0))
        self.assertGreater(displaced.common(main).Volume, 0.01)
        for angle in (-15, 15):
            displaced = shaft.copy()
            displaced.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertGreater(displaced.common(main).Volume, 1e-3)

    def test_radial_nut_and_screw_keep_open_loading_paths(self):
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

    def test_front_screws_and_adapter_clear_servo_during_bounded_rotation(self):
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

    def test_floor_and_oem_head_cavity_remain_without_a_fabricated_spline(self):
        from gondola.parts import servo_coupling as c

        main = c.adapter_shape()
        for x, z in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            section = Part.makeLine(
                App.Vector(x, c.OEM_HEAD_CAVITY_TOP_Y, z),
                App.Vector(x, c.SHAFT_START_Y, z),
            )
            self.assertAlmostEqual(main.common(section).Length, 1.5, places=6)
        head = Part.makeCylinder(2.2, 1.9, App.Vector(0, 3.5, 0), App.Vector(0, 1, 0))
        self.assertLess(main.common(head).Volume, 1e-7)
        self.assertIn("centre_screw_service", c.assembly_contract())


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
                [(0, 0, 0), (0, sign * 1.7, 0), (sign * 40, sign * 1.7, 0)],
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
            altered, [(0, 0, 0), (0, 1.7, 0), (40, 1.7, 0)], {}, SELECTED_DRIVE, 1
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
        waypoints = [(0, 0, 0), (0, 1.7, 0), (40, 1.7, 0)]
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
        midpoint = translated_shape(shape, 20, 1.7, 0)
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
