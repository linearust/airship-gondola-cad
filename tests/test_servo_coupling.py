"""Unmodified OEM horn, three M1 openings and external-hex fastener service."""

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
            self.assertEqual(screw_sku, "M1X6_HEX_HEAD")
            self.assertEqual(nut_sku, "M1_HEX_NUT")
            radius = 2.5 / math.sqrt(3)
            vertices = [
                App.Vector(
                    x + radius * math.cos(i * math.pi / 3),
                    0.5,
                    radius * math.sin(i * math.pi / 3),
                )
                for i in range(6)
            ]
            expected_head = Part.Face(
                Part.makePolygon(vertices + [vertices[0]])
            ).extrude(App.Vector(0, 1, 0))
            expected_screw = expected_head.fuse(
                Part.makeCylinder(0.5, 6.0, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0))
            )
            self.assertLess(expected_screw.cut(screw).Volume, 1e-7)
            self.assertLess(screw.cut(expected_screw).Volume, 1e-7)
            self.assertAlmostEqual(nut.BoundBox.YMin, 6.0, places=6)
            self.assertAlmostEqual(nut.BoundBox.YLength, 0.8, places=6)
            self.assertAlmostEqual(
                nut.Volume,
                (math.sqrt(3) / 2 * 2.5**2 - math.pi * 0.5**2) * 0.8,
                places=6,
            )
            self.assertAlmostEqual(screw.BoundBox.YMax - nut.BoundBox.YMax, 0.7)
            self.assertGreater(_plane_contact(c.horn_shape(), screw, 1.5), 1.0)
            self.assertGreater(_plane_contact(c.adapter_shape(), nut, 6.0), 1.0)

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
        # A circumscribed circle conservatively covers an AF2.5 nut at every yaw.
        # Include the slot's complete nominal shank-centre envelope.
        nut_radius = 2.5 / math.sqrt(3)
        for x in (12.8, 13.2, 13.6):
            for z in (-0.1, 0, 0.1):
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
        self.assertAlmostEqual(reported, 5.7)
        released = c.adapter_shape()
        released.translate(App.Vector(0, reported, 0))
        for name, screw, _ in c.horn_hardware_shapes():
            if name.endswith("Bolt"):
                self.assertGreaterEqual(
                    released.BoundBox.YMin - screw.BoundBox.YMax, 0.2 - 1e-6
                )

    def test_all_four_oem_holes_and_the_complete_source_shape_remain_unmodified(self):
        from gondola.parts import servo_coupling as c
        from gondola.parts.oem_servo_horn import normalized_shape

        manufacturer = normalized_shape()
        for selected in (c.horn_shape(),):
            self.assertLess(selected.cut(manufacturer).Volume, 1e-7)
            self.assertLess(manufacturer.cut(selected).Volume, 1e-7)
            self.assertAlmostEqual(selected.Volume, 202.72814863430688, places=6)
            for x, radius in ((4.5, 0.4), (6.8, 0.5), (10.0, 0.5), (13.2, 0.5)):
                passage = Part.makeCylinder(
                    radius, 2, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0)
                )
                outside = Part.makeCylinder(
                    radius + 0.1, 2, App.Vector(x, 1.5, 0), App.Vector(0, 1, 0)
                )
                self.assertLess(selected.common(passage).Volume, 1e-7)
                self.assertLess(outside.cut(passage).cut(selected).Volume, 1e-7)
        # Equal nominal diameters are tangent, not a supplied clearance promise.
        inner_m1 = Part.makeCylinder(
            0.5, 2, App.Vector(4.5, 1.5, 0), App.Vector(0, 1, 0)
        )
        self.assertAlmostEqual(
            manufacturer.common(inner_m1).Volume, math.pi * (0.5**2 - 0.4**2) * 2
        )
        self.assertFalse(c.assembly_contract()["horn_requires_drilling"])
        self.assertFalse(c.assembly_contract()["optional_middle_fastener_installed"])
        self.assertFalse(hasattr(c, "centering_jig_shape"))

    def test_near_round_hole_and_far_slot_keep_the_web_and_bounded_clearances(self):
        from gondola.parts import servo_coupling as c

        adapter = c.adapter_shape()
        for x, opening_length in ((6.8, 1.2), (10.0, 1.6), (13.2, 1.8)):
            for start, end, material in (
                ((x - 1.5, 5.0, 0), (x + 1.5, 5.0, 0), 3.0 - opening_length),
                ((x, 5.0, -2), (x, 5.0, 2), 4.0 - 1.2),
            ):
                section = Part.makeLine(App.Vector(*start), App.Vector(*end))
                self.assertAlmostEqual(adapter.common(section).Length, material)
        for xmin, xmax, length in ((7.4, 9.2, 1.8), (10.8, 12.3, 1.5)):
            web = Part.makeBox(xmax - xmin, 2.5, 1.2, App.Vector(xmin, 3.5, -0.6))
            self.assertLess(web.cut(adapter).Volume, 1e-7)
            self.assertAlmostEqual(web.BoundBox.XLength, length)
        for name, shape, _ in c.horn_hardware_shapes():
            limit = 0.1 if name.startswith("Near") else 0.4
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
        for shift, blocked in ((-0.09, False), (-0.11, True)):
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
            limit = 0.1 if name.startswith("Near") else 0.4
            for offset in (-limit, 0.0, limit):
                moved = nut.copy()
                moved.translate(App.Vector(offset, 0, 0))
                self.assertGreaterEqual(_plane_contact(adapter, moved, 6.0), 1.0)
        for x, limit in ((6.8, 0.1), (13.2, 0.4)):
            minimum_nut = purchased_hardware.hex_prism(2.4, 0.8).cut(
                Part.makeCylinder(0.5, 1.0, App.Vector(0, 0, -0.1))
            )
            for offset in (-limit, 0.0, limit):
                moved = minimum_nut.copy()
                moved.Placement = App.Placement(
                    App.Vector(x + offset, 6.0, 0),
                    App.Rotation(App.Vector(0, 0, 1), App.Vector(0, 1, 0)),
                )
                self.assertGreaterEqual(_plane_contact(adapter, moved, 6.0), 1.0)

    def test_recessed_minimum_nuts_float_radially_but_cannot_spin(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import nut_recess_check

        adapter = c.adapter_shape()
        for x, allowance in ((6.8, 0.0), (13.2, 0.3)):
            with self.subTest(radius=x):
                capture = nut_recess_check(adapter, x, allowance)
                self.assertTrue(capture["passed"], capture)
                # An oversized shallow round pocket preserves the floor but
                # loses the flanks that prevent a minimum AF2.4 nut spinning.
                damaged = adapter.cut(
                    Part.makeCylinder(
                        2.5, 1.2, App.Vector(x, 6.0, 0), App.Vector(0, 1, 0)
                    )
                )
                failed = nut_recess_check(damaged, x, allowance)
                self.assertFalse(failed["passed"], failed)
                self.assertEqual(failed["retained_floor_lengths_mm"], [2.5, 2.5])
        self.assertAlmostEqual(c.assembly_contract()["fastener_grip_mm"], 2.5)

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

    def test_three_opening_witness_rejects_middle_plug_and_thinned_web(self):
        from gondola.parts import servo_coupling as c
        from gondola.validation.horn_coupling import factory_opening_check

        horn, adapter = c.horn_shape(), c.adapter_shape()
        self.assertTrue(factory_opening_check(horn, adapter)["passed"])
        plug = Part.makeCylinder(0.55, 2.5, App.Vector(10, 3.5, 0), App.Vector(0, 1, 0))
        blocked = factory_opening_check(horn, adapter.fuse(plug))
        self.assertFalse(blocked["passed"])
        self.assertGreater(blocked["adapter_openings"][1]["blocked_mm3"], 1)
        cut = Part.makeBox(0.2, 2.5, 1.2, App.Vector(10.8, 3.5, -0.6))
        thinned = factory_opening_check(horn, adapter.cut(cut))
        self.assertFalse(thinned["passed"])
        self.assertGreater(thinned["retained_floor_webs"][1]["missing_stock_mm3"], 0.5)
        enlarged = horn.cut(
            Part.makeCylinder(0.55, 2, App.Vector(10, 1.5, 0), App.Vector(0, 1, 0))
        )
        modified = factory_opening_check(enlarged, adapter)
        self.assertFalse(modified["passed"])
        self.assertGreater(modified["factory_holes"][2]["missing_ring_mm3"], 0.3)

    def test_external_hex_tool_fits_default_end_pair_but_not_three_bolt_candidate(self):
        from gondola.parts import servo_coupling as c

        hardware = {name: shape for name, shape, _ in c.horn_hardware_shapes()}
        retained = {
            "servo": self._servo_envelope(),
            "horn": c.horn_shape(),
            "adapter": c.adapter_shape(),
            **hardware,
        }
        for label, x, clearance in (("Near", 6.8, 0.45), ("Far", 13.2, 6.85)):
            # Full socket exterior through the head's entire engagement height,
            # excluding only the driven bolt inside its internal socket.
            tool = Part.makeCylinder(
                2.85, 60, App.Vector(x, 1.5, 0), App.Vector(0, -1, 0)
            )
            for name, shape in retained.items():
                if name != label + "Bolt":
                    self.assertLess(tool.common(shape).Volume, 1e-7, name)
            self.assertAlmostEqual(tool.distToShape(retained["servo"])[0], clearance)
        middle_bolt = hardware["NearBolt"].copy()
        middle_bolt.translate(App.Vector(3.2, 0, 0))
        self.assertLess(middle_bolt.common(retained["horn"]).Volume, 1e-7)
        self.assertLess(middle_bolt.common(retained["adapter"]).Volume, 1e-7)
        for x in (6.8, 13.2):
            tool = Part.makeCylinder(
                2.85, 60, App.Vector(x, 1.5, 0), App.Vector(0, -1, 0)
            )
            self.assertGreater(tool.common(middle_bolt).Volume, 0.1)
        self.assertFalse(c.assembly_contract()["optional_middle_fastener_installed"])

    def test_metal_stub_retains_stop_flat_and_gear_end_reserve(self):
        from gondola.parts import servo_coupling as c

        main, shaft = c.adapter_shape(), c.driver_shaft_shape()
        self.assertAlmostEqual(shaft.BoundBox.YLength, 20)
        unclocked = shaft.copy()
        unclocked.rotate(App.Vector(), App.Vector(0, 1, 0), -c.SHAFT_CLAMP_CLOCK_DEG)
        self.assertAlmostEqual(unclocked.BoundBox.XMin, -1)
        self.assertAlmostEqual(shaft.BoundBox.YMax, c.GEAR_START_Y + 12)
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
                    self.assertAlmostEqual(result["metal_projection_beyond_gear_mm"], 4)
            finally:
                pod.Tilt = original
                self.doc.recompute()

    def test_jack_reacts_at_centred_shaft_before_any_radial_take_up(self):
        from gondola.validation.propulsion import input_shaft_retention_check

        for prefix in ("Port", "Starboard"):
            report = input_shaft_retention_check(self.doc, prefix)
            self.assertTrue(report["passed"], report)
            reaction = report["centred_jack_reaction"]
            self.assertAlmostEqual(reaction["centred_reaction_contact_length_mm"], 7.8)
            self.assertGreater(reaction["jack_direction_probe_penetration_mm3"], 0.01)

    def test_old_radial_socket_clearance_cannot_pass_the_centred_reaction_check(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.propulsion import input_shaft_retention_check

        adapter = self.doc.PortHornGearAdapter
        original = adapter.Shape.copy()
        try:
            # Restore the old 0.05mm radial gap without disturbing the stop,
            # flat, tip contact, nut, or full-length metal journal.
            relief = coupling.shaft_frame_shape(coupling._d_section(7.1, 8.1, 0.05))
            relief.translate(App.Vector(0, coupling.HORN_BOTTOM_Y, 0))
            adapter.Shape = original.cut(relief).removeSplitter()
            self.doc.recompute()
            report = input_shaft_retention_check(self.doc, "Port")
            self.assertFalse(report["passed"], report)
            self.assertGreater(report["screw_tip_to_flat_contact_mm2"], 1)
            self.assertGreater(report["shaft_stop_contact_mm2"], 1)
            reaction = report["centred_jack_reaction"]
            self.assertLess(reaction["centred_reaction_contact_length_mm"], 1e-7)
            self.assertLess(reaction["jack_direction_probe_penetration_mm3"], 1e-7)
        finally:
            adapter.Shape = original
            self.doc.recompute()

    def test_full_gear_engagement_does_not_hide_a_missing_end_reserve(self):
        from gondola.parts import servo_coupling as coupling
        from gondola.validation.propulsion import direct_adapter_fit_check

        shaft = self.doc.PortInputShaft
        original = shaft.Shape.copy()
        try:
            # Keep the entire socket and selected gear journal, but remove the
            # four-millimetre projection beyond the gear's front face.
            shaft.Shape = original.cut(
                Part.makeBox(
                    6,
                    5,
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
            from gondola.parts import servo_coupling as c

            screw.Placement.Base += c.shaft_frame_point(-0.3, 0, 0)
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
                from gondola.parts import servo_coupling as c

                nut.Placement.Base += c.shaft_frame_point(displacement, 0, 0)
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
                coupling.HORN_BOTTOM_Y + coupling.BODY_BACK_Y + 3.5 - 8,
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
