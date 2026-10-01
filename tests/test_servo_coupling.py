"""Prepared OEM horn, near registration hole, far slot and metal shaft retention."""

import math
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
        from gondola.parts import servo_coupling as c
        from gondola.parts import servo_envelope

        shape = servo_envelope.shape()
        shape.translate(App.Vector(0, -c.HORN_BOTTOM_Y, 0))
        return shape

    @staticmethod
    def _clamp_hardware():
        from gondola.parts import servo_coupling as c

        return [shape for _, shape, _ in c.horn_hardware_shapes()]

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

    def test_selected_horn_and_rear_bolts_front_nuts_clear_the_transmission(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import _plane_contact

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
        self.assertEqual(c.HORN_SKU, "KST_X06_STOCK_HALF_ARM_1")
        self.assertEqual(c.BOLT_DIRECTION, (0, 1, 0))
        hardware = {name: (shape, sku) for name, shape, sku in c.horn_hardware_shapes()}
        self.assertEqual(set(hardware), {"NearBolt", "NearNut", "FarBolt", "FarNut"})
        for label, x in (("Near", 6.8), ("Far", 13.2)):
            screw, screw_sku = hardware[label + "Bolt"]
            nut, nut_sku = hardware[label + "Nut"]
            self.assertEqual(screw_sku, "M1_4X8_PAN_HEAD_KIT")
            self.assertEqual(nut_sku, "M1_4_HEX_NUT_DIN934")
            expected_screw = Part.makeCylinder(
                1.3, 1.0, App.Vector(x, 0.5, 0), App.Vector(0, 1, 0)
            ).fuse(
                Part.makeCylinder(0.7, 8.0, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0))
            )
            self.assertLess(expected_screw.cut(screw).Volume, 1e-7)
            self.assertLess(screw.cut(expected_screw).Volume, 1e-7)
            self.assertAlmostEqual(nut.BoundBox.YMin, 6.5, places=6)
            self.assertAlmostEqual(nut.BoundBox.YLength, 1.2, places=6)
            self.assertAlmostEqual(
                nut.Volume,
                (math.sqrt(3) / 2 * 3.0**2 - math.pi * 0.7**2) * 1.2,
                places=6,
            )
            self.assertAlmostEqual(screw.BoundBox.YMax - nut.BoundBox.YMax, 1.8)
            self.assertGreater(_plane_contact(c.horn_shape(), screw, 1.5), 1.0)
            self.assertGreater(_plane_contact(c.adapter_shape(), nut, 6.5), 1.0)

    def test_taper_keeps_oem_face_support_and_far_nut_seat_at_slot_limits(self):
        from gondola.parts import servo_coupling as c

        blank = c.plate_blank()
        self.assertTrue(blank.isValid())
        self.assertEqual(len(blank.Solids), 1)
        # The entire supplied blade top silhouette remains within the new taper;
        # root-screw cavity and fastener openings are tested separately.
        face_slice = c.horn_shape().common(
            Part.makeBox(40, 0.001, 20, App.Vector(-10, 3.499, -10))
        )
        face_slice.translate(App.Vector(0, 0.002, 0))
        self.assertLess(face_slice.cut(blank).Volume, 1e-8)
        old_rectangle = Part.makeBox(22.5, 3.6, 10.3, App.Vector(-6.5, 3.5, -5.15))
        self.assertGreater(old_rectangle.cut(blank).Volume, 250)
        # A circumscribed circle conservatively covers an AF3 nut at every yaw.
        # Include the slot's complete nominal shank-centre envelope.
        nut_radius = 3.0 / math.sqrt(3)
        for x in (12.7, 13.2, 13.7):
            for z in (-0.2, 0, 0.2):
                seat = Part.makeCylinder(
                    nut_radius, 0.01, App.Vector(x, 7.09, z), App.Vector(0, 1, 0)
                )
                self.assertLess(seat.cut(blank).Volume, 1e-8)
        self.assertGreaterEqual(
            c.PLATE_TIP_RADIUS - c.SLOT_WIDTH / 2 - c.HORN_ADAPTER_SLOT_ALLOWANCE, 1.5
        )

    def test_reported_adapter_release_clears_retained_horn_screw_tips(self):
        from gondola.parts import servo_coupling as c

        reported = c.metrics()["adapter_axial_release_travel_mm"]
        self.assertAlmostEqual(reported, 7.7)
        released = c.adapter_shape()
        released.translate(App.Vector(0, reported, 0))
        for name, screw, _ in c.horn_hardware_shapes():
            if name.endswith("Bolt"):
                self.assertGreaterEqual(
                    released.BoundBox.YMin - screw.BoundBox.YMax, 0.2 - 1e-6
                )

    def test_only_two_selected_factory_holes_are_prepared(self):
        from gondola.parts import servo_coupling as c
        from gondola.parts.oem_servo_horn import normalized_shape

        original, prepared = c.horn_shape(prepared=False), c.horn_shape()
        manufacturer = normalized_shape()
        self.assertLess(original.cut(manufacturer).Volume, 1e-7)
        self.assertLess(manufacturer.cut(original).Volume, 1e-7)
        expected = original.copy()
        for x in (6.8, 13.2):
            expected = expected.cut(
                Part.makeCylinder(0.75, 2.2, App.Vector(x, 1.4, 0), App.Vector(0, 1, 0))
            )
        self.assertLess(expected.cut(prepared).Volume, 1e-7)
        self.assertLess(prepared.cut(expected).Volume, 1e-7)
        self.assertAlmostEqual(
            original.Volume - prepared.Volume,
            2 * math.pi * (0.75**2 - 0.5**2) * 2.0,
            delta=1e-6,
        )
        for x, original_radius in ((4.5, 0.4), (6.8, 0.5), (10.0, 0.5), (13.2, 0.5)):
            radius = 0.75 if x in (6.8, 13.2) else original_radius
            factory_passage = Part.makeCylinder(
                original_radius, 2.0, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0)
            )
            self.assertLess(original.common(factory_passage).Volume, 1e-7)
            passage = Part.makeCylinder(
                radius, 2.0, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0)
            )
            surrounding = Part.makeCylinder(
                radius + 0.1, 2.0, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0)
            )
            self.assertLess(prepared.common(passage).Volume, 1e-7)
            self.assertAlmostEqual(
                prepared.common(surrounding).Volume,
                math.pi * ((radius + 0.1) ** 2 - radius**2) * 2.0,
                places=6,
            )
        self.assertTrue(
            all(set(anchors) == {"screw", "nut"} for anchors in c.fastener_positions())
        )
        self.assertFalse(hasattr(c, "centering_jig_shape"))

    def test_near_round_hole_and_far_slot_keep_the_web_and_bounded_clearances(self):
        from gondola.parts import servo_coupling as c

        adapter = c.adapter_shape()
        for x, opening_length in ((6.8, 1.8), (13.2, 2.4)):
            for start, end, material in (
                ((x - 2, 5.3, 0), (x + 2, 5.3, 0), 4.0 - opening_length),
                ((x, 5.3, -2), (x, 5.3, 2), 4.0 - 1.8),
            ):
                section = Part.makeLine(App.Vector(*start), App.Vector(*end))
                self.assertAlmostEqual(adapter.common(section).Length, material)
        web = Part.makeBox(3.8, 3.0, 1.8, App.Vector(8.1, 3.5, -0.9))
        self.assertLess(web.cut(adapter).Volume, 1e-7)
        for name, shape, _ in c.horn_hardware_shapes():
            limit = 0.2 if name.startswith("Near") else 0.5
            for shift in (-limit, limit):
                moved = shape.copy()
                moved.translate(App.Vector(shift, 0, 0))
                self.assertLess(moved.common(adapter).Volume, 1e-7)
            if name.endswith("Bolt"):
                for shift in (-limit - 0.01, limit + 0.01):
                    moved = shape.copy()
                    moved.translate(App.Vector(shift, 0, 0))
                    self.assertGreater(moved.common(adapter).Volume, 1e-4)

    def test_near_hole_bounds_the_open_register_direction_while_far_slot_fits_pitch(
        self,
    ):
        from gondola.parts import servo_coupling as c

        adapter, horn = c.adapter_shape(), c.horn_shape()
        hardware = {name: shape for name, shape, _ in c.horn_hardware_shapes()}
        for shift, blocked in ((-0.19, False), (-0.21, True)):
            moved = adapter.copy()
            moved.translate(App.Vector(shift, 0, 0))
            # The purchased taper clears this direction. The near round hole,
            # rather than an invented front root arc, must bound translation.
            self.assertLess(moved.common(horn).Volume, 1e-7)
            self.assertLess(moved.common(hardware["FarBolt"]).Volume, 1e-7)
            near_overlap = moved.common(hardware["NearBolt"]).Volume
            if blocked:
                self.assertGreater(near_overlap, 1e-4)
            else:
                self.assertLess(near_overlap, 1e-7)
        for pitch_error in (-0.3, 0.3):
            # A relative far-hole/bolt pitch error does not require moving the
            # near datum or widening its round opening.
            far = hardware["FarBolt"].copy()
            far.translate(App.Vector(pitch_error, 0, 0))
            self.assertLess(far.common(adapter).Volume, 1e-7)

    def test_open_register_blocks_rearward_and_side_motion(self):
        from gondola.parts import servo_coupling as c

        adapter, horn = c.adapter_shape(), c.horn_shape()
        for x, z in ((0.29, 0), (0, -0.29), (0, 0.29)):
            moved = adapter.copy()
            moved.translate(App.Vector(x, 0, z))
            self.assertGreater(moved.common(horn).Volume, 1e-4)

    def test_front_nuts_bear_on_both_openings_through_the_shank_clearance(self):
        from gondola.parts import purchased_hardware
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import _plane_contact

        adapter = c.adapter_shape()
        for name, nut, _ in c.horn_hardware_shapes():
            if not name.endswith("Nut"):
                continue
            limit = 0.2 if name.startswith("Near") else 0.5
            for offset in (-limit, 0.0, limit):
                moved = nut.copy()
                moved.translate(App.Vector(offset, 0, 0))
                self.assertGreaterEqual(_plane_contact(adapter, moved, 6.5), 1.0)
        for x, limit in ((6.8, 0.2), (13.2, 0.5)):
            minimum_nut = purchased_hardware.hex_prism(2.9, 1.2).cut(
                Part.makeCylinder(0.7, 1.4, App.Vector(0, 0, -0.1))
            )
            for offset in (-limit, 0.0, limit):
                moved = minimum_nut.copy()
                moved.Placement = App.Placement(
                    App.Vector(x + offset, 6.5, 0),
                    App.Rotation(App.Vector(0, 0, 1), App.Vector(0, 1, 0)),
                )
                self.assertGreaterEqual(_plane_contact(adapter, moved, 6.5), 1.0)

    def test_recessed_minimum_nuts_float_radially_but_cannot_spin(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import nut_recess_check

        adapter = c.adapter_shape()
        for x, allowance in ((6.8, 0.0), (13.2, 0.3)):
            with self.subTest(radius=x):
                capture = nut_recess_check(adapter, x, allowance)
                self.assertTrue(capture["passed"], capture)
                # An oversized shallow round pocket preserves the floor but
                # loses the flanks that prevent a minimum AF2.9 nut spinning.
                damaged = adapter.cut(
                    Part.makeCylinder(
                        2.5, 0.7, App.Vector(x, 6.5, 0), App.Vector(0, 1, 0)
                    )
                )
                failed = nut_recess_check(damaged, x, allowance)
                self.assertFalse(failed["passed"], failed)
                self.assertEqual(failed["retained_floor_lengths_mm"], [3.0, 3.0])
        self.assertAlmostEqual(c.assembly_contract()["fastener_grip_mm"], 3.0)

    def test_front_nuts_release_off_bridge_while_rear_bolts_remain(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.propulsion_service import continuous_path

        # Driver gear and stub have already left the complete servo unit.
        hardware = {name: shape for name, shape, _ in c.horn_hardware_shapes()}
        fixed = {
            "adapter": c.adapter_shape(),
            "horn": c.horn_shape(),
            "servo": self._servo_envelope(),
            **hardware,
        }
        for name in ("FarNut", "NearNut"):
            with self.subTest(joint=name):
                nut = fixed.pop(name)
                result = continuous_path(
                    nut, [(0, 0, 0), (0, 3.2, 0), (20, 3.2, 0)], fixed
                )
                self.assertTrue(result["passed"], result)
        self.assertIn("NearBolt", fixed)
        self.assertIn("FarBolt", fixed)

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

    def test_all_horn_fasteners_and_adapter_clear_servo_during_bounded_rotation(self):
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
        from gondola.validation.propulsion_service import (
            adapter_service_check,
            module_service_shapes,
        )

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
        from gondola.validation.propulsion_service import (
            adapter_service_check,
            module_service_shapes,
        )

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
        from gondola.validation.propulsion_service import (
            adapter_service_check,
            module_service_shapes,
        )

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
                SELECTED_DRIVE.input_z_mm + 2.0,
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
