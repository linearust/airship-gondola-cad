"""Physical fit and assembly paths for the direct stock-horn gear adapter."""

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

        anchors = coupling.fastener_positions()[0]
        rotation = App.Rotation(
            App.Vector(0, 0, 1), App.Vector(*coupling.BOLT_DIRECTION)
        )
        result = []
        for shape, anchor in (
            (hardware.screw_shape(), anchors["screw"]),
            (hardware.hex_nut_shape(), anchors["nut"]),
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
        # Tip cylinder conservatively includes every tooth; the gear itself is
        # bought and must retain the selected seller's complete axial stack.
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

    def test_stock_horn_gear_and_fasteners_fit_without_drilling_the_horn(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.parts import servo_coupling as coupling

        self.assertEqual(SELECTED_DRIVE.driver.bore_mm, coupling.GEAR_BORE_DIAMETER)
        self.assertEqual(SELECTED_DRIVE.driver.total_length_mm, coupling.GEAR_LENGTH)
        main = coupling.adapter_shape()
        retainer = coupling.retainer_shape()
        horn = coupling.horn_shape()
        gear = self._driver_gear()
        shaft = coupling.driver_shaft_shape()
        screw, nut = self._clamp_hardware()
        radial_screw, radial_nut = self._shaft_clamp_hardware()
        shapes = [
            main,
            retainer,
            horn,
            gear,
            shaft,
            screw,
            nut,
            radial_screw,
            radial_nut,
        ]
        for shape in shapes:
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids), 1)
        for index, first in enumerate(shapes):
            for second in shapes[index + 1 :]:
                self.assertLess(first.common(second).Volume, 1e-7)
        self.assertAlmostEqual(main.distToShape(gear)[0], 0, places=6)
        self.assertAlmostEqual(shaft.distToShape(gear)[0], 0, places=6)
        self.assertAlmostEqual(shaft.distToShape(radial_screw)[0], 0, places=6)
        self.assertAlmostEqual(main.distToShape(radial_nut)[0], 0, places=6)
        self.assertAlmostEqual(main.distToShape(radial_screw)[0], 0.1, places=6)
        head = radial_screw.common(
            Part.makeBox(3, 5, 5, App.Vector(7, coupling.SHAFT_CLAMP_Y - 2.5, -2.5))
        )
        self.assertAlmostEqual(head.distToShape(main)[0], 0.5, places=6)
        self.assertGreater(head.distToShape(gear)[0], 1.5)
        self.assertAlmostEqual(main.distToShape(horn)[0], 0, places=6)
        self.assertAlmostEqual(retainer.distToShape(horn)[0], 0, places=6)

    def test_metal_stub_seats_in_adapter_and_key_cannot_turn_freely(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        shaft = coupling.driver_shaft_shape()
        self.assertAlmostEqual(shaft.BoundBox.YLength, 16, places=6)
        self.assertAlmostEqual(shaft.BoundBox.XMax, 1, places=6)
        self.assertAlmostEqual(shaft.BoundBox.YMax, coupling.GEAR_START_Y + 8, places=6)
        displaced = shaft.copy()
        displaced.translate(App.Vector(0, -0.01, 0))
        self.assertGreater(displaced.common(main).Volume, 1e-5)
        for angle in (-15, 15):
            displaced = shaft.copy()
            displaced.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertGreater(displaced.common(main).Volume, 1e-3)
        # The D key is an anti-rotation interface, not an axial locking feature.
        # Forward retention comes from the radial screw and must be load-tested.
        displaced = shaft.copy()
        displaced.translate(App.Vector(0, 0.5, 0))
        self.assertLess(displaced.common(main).Volume, 1e-7)

    def test_radial_nut_and_screw_have_open_loading_paths(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        gear = self._driver_gear()
        shaft = coupling.driver_shaft_shape()
        screw, nut = self._shaft_clamp_hardware()
        for step in range(1, 21):
            lifted = nut.copy()
            lifted.translate(App.Vector(0, 0, step * 0.5))
            for obstacle in (main, shaft, gear):
                self.assertLess(lifted.common(obstacle).Volume, 1e-7)
            withdrawn = screw.copy()
            withdrawn.translate(App.Vector(step * 0.5, 0, 0))
            for obstacle in (main, shaft, nut, gear):
                self.assertLess(withdrawn.common(obstacle).Volume, 1e-7)

    def test_shallow_socket_centres_the_horn_and_clamps_before_the_parts_bottom(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        retainer = coupling.retainer_shape()
        horn = coupling.horn_shape()
        registers = [
            face
            for face in main.Faces
            if type(face.Surface).__name__ == "Cylinder"
            and abs(face.Surface.Radius - 3.05) < 1e-7
        ]
        self.assertTrue(registers)
        for face in registers:
            self.assertAlmostEqual(face.BoundBox.YLength, 1.3, places=6)
            self.assertAlmostEqual(face.BoundBox.YMax, 3.5, places=6)
        self.assertAlmostEqual(main.distToShape(retainer)[0], 0.3, places=6)
        for direction, obstacle in ((1, main), (-1, retainer)):
            displaced = horn.copy()
            displaced.translate(App.Vector(0, direction * 0.01, 0))
            self.assertGreater(displaced.common(obstacle).Volume, 1e-5)

    def test_relaxed_flanks_preserve_hub_and_tip_position_datums(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        horn = coupling.horn_shape()
        # Side relief must not turn into free translation of the input axis.
        # The open root circle needs its opposing flat tip stop for +X.
        for dx, dz in ((0.1, 0), (-0.1, 0), (0, 0.1), (0, -0.1)):
            displaced = horn.copy()
            displaced.translate(App.Vector(dx, 0, dz))
            self.assertGreater(displaced.common(main).Volume, 1e-4)
        # A wider blade is accepted with the same hub and overall length.
        # Trimming the end preserves the deliberately critical tip datum.
        wider_blade = coupling._tangent_hull(1.9, 1.6, 3, 2.2, 13.2)
        wider_blade = wider_blade.common(
            Part.makeBox(20.2, 2, 10, App.Vector(-5, 1.7, -5))
        )
        self.assertLess(main.common(wider_blade).Volume, 1e-7)
        for angle in (-3, 3):
            turned = horn.copy()
            turned.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
            self.assertGreater(turned.common(main).Volume, 1e-3)

    def test_parts_install_around_an_already_retained_horn_at_neutral(self):
        from gondola.parts import servo_coupling as coupling

        main = coupling.adapter_shape()
        retainer = coupling.retainer_shape()
        horn = coupling.horn_shape()
        case = self._servo_envelope()
        for step in range(1, 51):
            distance = step * 0.5
            incoming = main.copy()
            incoming.translate(App.Vector(0, distance, 0))
            self.assertLess(incoming.common(horn).Volume, 1e-7)
            incoming = retainer.copy()
            incoming.translate(App.Vector(0, -distance, 0))
            for obstacle in (main, horn, case):
                self.assertLess(incoming.common(obstacle).Volume, 1e-7)

    def test_rear_clamp_head_clears_servo_through_full_input_travel(self):
        from gondola.parts import servo_coupling as coupling

        case = self._servo_envelope()
        moving = [
            coupling.adapter_shape(),
            coupling.retainer_shape(),
            coupling.driver_shaft_shape(),
            *self._clamp_hardware(),
            *self._shaft_clamp_hardware(),
        ]
        for angle in range(-60, 61, 5):
            for shape in moving:
                rotated = shape.copy()
                rotated.rotate(App.Vector(), App.Vector(0, 1, 0), angle)
                self.assertLess(rotated.common(case).Volume, 1e-7)
                self.assertGreaterEqual(rotated.distToShape(case)[0], 0.6 - 1e-7)

    def test_functional_walls_and_separate_open_pockets_remain_manufacturable(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.manufacturing import planar_wall_regions

        main = coupling.adapter_shape()
        for shape in (main, coupling.retainer_shape()):
            thin = [
                row
                for row in planar_wall_regions(shape)
                if row["material_thickness_mm"] < 1.5 - 1e-6
            ]
            self.assertEqual(thin, [])
        self.assertGreaterEqual(
            coupling.SHAFT_BOSS_END_X - coupling.SHAFT_NUT_SEAT_X, 1.5
        )
        # Both blind cavities have their own exterior opening. A full roof,
        # including the centre, isolates the retained OEM screw from the shaft.
        axis = App.Vector(0, 1, 0)
        head_cavity = Part.makeCylinder(2.5, 5.3, App.Vector(0, -0.1, 0), axis)
        self.assertLess(main.common(head_cavity).Volume, 1e-7)
        shaft_path = coupling.driver_shaft_shape()
        shaft_path.translate(App.Vector(0, 1, 0))
        self.assertLess(main.common(shaft_path).Volume, 1e-7)
        centre = Part.makeLine(App.Vector(0, 5.2, 0), App.Vector(0, 7.1, 0))
        self.assertAlmostEqual(main.common(centre).Length, 1.9, places=6)
        for x, z in ((2, 0), (-2, 0), (0, 2), (0, -2)):
            section = Part.makeLine(
                App.Vector(x, -0.1, z), App.Vector(x, coupling.SHAFT_START_Y, z)
            )
            self.assertAlmostEqual(main.common(section).Length, 1.9, places=6)


@unittest.skipIf(App is None, "Requires FreeCAD")
class InputShaftEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("InputShaftEvidenceRegression")
        cls.module = propulsion.build_propulsion_module(cls.doc)
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
            finally:
                pod.Tilt = original
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
            screw.Placement.Base += App.Vector(0.3, 0, 0)
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
                nut.Placement.Base += App.Vector(displacement, 0, 0)
                self.doc.recompute()
                result = input_shaft_retention_check(self.doc, "Port")
                self.assertFalse(result["passed"], result)
                self.assertLess(result["nut_to_retaining_wall_contact_mm2"], 1e-7)
        finally:
            nut.Placement = original
            self.doc.recompute()

    def test_adapter_continuous_service_preserves_the_retained_horn_socket(self):
        from gondola.contracts.drive import SELECTED_DRIVE
        from gondola.validation.propulsion import _service_shapes, adapter_service_check

        shapes, missing = _service_shapes(self.doc, self.module)
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
        from gondola.validation.propulsion import _service_shapes, adapter_service_check

        shapes, _ = _service_shapes(self.doc, self.module)
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
        from gondola.validation.propulsion import _service_shapes, adapter_service_check

        shapes, _ = _service_shapes(self.doc, self.module)
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
