"""Native CAD regressions; run with the installed FreeCAD Python runtime."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from gondola.contracts.drive import DRIVE_CONFIGURATIONS, SELECTED_DRIVE

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class ContinuousServiceTests(unittest.TestCase):
    def test_midpath_obstacle_is_not_hidden_by_clear_endpoints(self):
        from gondola.cad import translated_shape
        from gondola.validation.geometry import intersection_volume
        from gondola.validation.propulsion import continuous_path

        moving = Part.makeBox(0.1, 1, 1)
        obstacle = Part.makeBox(0.02, 1, 1, App.Vector(5.37, 0, 0))
        self.assertEqual(intersection_volume(moving, obstacle), 0)
        self.assertEqual(
            intersection_volume(translated_shape(moving, x=10), obstacle), 0
        )
        result = continuous_path(
            moving, [(0, 0, 0), (10, 0, 0)], {"thin_wall": obstacle}
        )
        self.assertFalse(result["passed"])
        self.assertGreater(result["segments"][0]["intersection_mm3"]["thin_wall"], 0)

    def test_coaxial_sweep_keeps_a_real_through_bore_open(self):
        from gondola.validation.geometry import intersection_volume, translation_sweep

        sleeve = Part.makeCylinder(2, 2).cut(Part.makeCylinder(1, 2))
        swept, method = translation_sweep(sleeve, (0, 0, 8))
        expected = Part.makeCylinder(2, 10).cut(Part.makeCylinder(1, 10))
        self.assertIn("face-prism", method)
        self.assertLess(abs(expected.cut(swept).Volume), 1e-7)
        self.assertLess(abs(swept.cut(expected).Volume), 1e-7)
        self.assertEqual(intersection_volume(swept, Part.makeCylinder(0.5, 10)), 0)

    def test_transverse_cylinder_uses_a_conservative_envelope(self):
        from gondola.cad import translated_shape
        from gondola.validation.geometry import translation_sweep

        moving = Part.makeCylinder(1, 2)
        swept, method = translation_sweep(moving, (-10, 0, 0))
        self.assertIn("conservative", method)
        for distance in (0, -0.13, -4.57, -10):
            self.assertLess(
                abs(translated_shape(moving, x=distance).cut(swept).Volume), 1e-7
            )

    def test_invalid_displacement_is_rejected(self):
        from gondola.validation.geometry import translation_sweep

        with self.assertRaises(ValueError):
            translation_sweep(Part.makeBox(1, 1, 1), (float("nan"), 0, 0))


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class GearEngagementTests(unittest.TestCase):
    def gears(self):
        def gear(radius, hub_radius, x):
            axis = App.Vector(0, 1, 0)
            origin = App.Vector(x, 0, 0)
            return Part.makeCylinder(radius, 3, origin, axis).fuse(
                Part.makeCylinder(hub_radius, 8, origin, axis)
            )

        return gear(15.5, 6, 0), gear(5.5, 3.5, 20)

    def check(self, driver, output):
        from gondola.validation.propulsion import gear_mesh_check

        return gear_mesh_check(
            driver,
            output,
            module=0.5,
            driver_teeth=60,
            output_teeth=20,
            minimum_face_overlap=3,
        )

    def test_aligned_tooth_faces_pass_positioning_check(self):
        result = self.check(*self.gears())
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["tooth_face_overlap_mm"], 3)

    def test_overlapping_hub_lengths_cannot_hide_disengaged_tooth_faces(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        output = translated_shape(output, y=3.2)
        self.assertLess(output.BoundBox.YMin, driver.BoundBox.YMax)
        result = self.check(driver, output)
        self.assertFalse(result["passed"], result)
        self.assertLess(result["tooth_face_overlap_mm"], 0)

    def test_axis_distance_must_match_the_fixed_nominal_datum(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        for shift in (-0.1, 0.05):
            with self.subTest(shift=shift):
                result = self.check(driver, translated_shape(output, x=shift))
                self.assertFalse(result["passed"], result)

    def test_nominal_axis_tolerance_cannot_hide_insufficient_contact_ratio(self):
        from gondola.cad import translated_shape

        driver, output = self.gears()
        result = self.check(driver, translated_shape(output, x=0.2))
        self.assertAlmostEqual(result["axis_distance_mm"], 20.2)
        self.assertLess(result["standard_involute_contact_ratio"], 1.3)
        self.assertFalse(result["passed"], result)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class BearingCaptureTests(unittest.TestCase):
    def stack(self):
        axis = App.Vector(0, 1, 0)

        def annulus(outer, inner, length, y):
            origin = App.Vector(0, y, 0)
            return Part.makeCylinder(outer, length, origin, axis).cut(
                Part.makeCylinder(inner, length, origin, axis)
            )

        bearing = annulus(3, 1.5, 2.5, 0)
        shaft = Part.makeCylinder(1.5, 6, App.Vector(0, -1, 0), axis)
        seat = annulus(4.5, 2, 1.5, -1.5).fuse(annulus(4.5, 3.2, 2.5, 0))
        cap = annulus(4.5, 2, 1.5, 2.5)
        return bearing, shaft, seat, cap

    def test_nominal_stock_bearing_is_captured_with_clear_full_length_shaft(self):
        from gondola.validation.propulsion import bearing_stack_check

        result = bearing_stack_check(*self.stack())
        self.assertTrue(result["passed"], result)

    def test_missing_cap_is_not_axial_retention(self):
        from gondola.validation.propulsion import bearing_stack_check

        bearing, shaft, seat, _ = self.stack()
        result = bearing_stack_check(bearing, shaft, seat, Part.Shape())
        self.assertFalse(result["passed"])
        self.assertFalse(result["axial_capture"][1]["passed"])

    def test_offset_bearing_fails_even_when_the_stock_dimensions_match(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import bearing_stack_check

        bearing, shaft, seat, cap = self.stack()
        result = bearing_stack_check(translated_shape(bearing, x=0.2), shaft, seat, cap)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["shaft_axis_error_mm"], 0.2)

    def test_short_shaft_cannot_claim_full_inner_ring_engagement(self):
        from gondola.validation.propulsion import bearing_stack_check

        bearing, _, seat, cap = self.stack()
        short_shaft = Part.makeCylinder(
            1.5, 1.5, App.Vector(0, 0, 0), App.Vector(0, 1, 0)
        )
        result = bearing_stack_check(bearing, short_shaft, seat, cap)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["shaft_through_bearing_length_mm"], 1.5)


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class NativeGearedDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.doc = App.newDocument("GearedDriveRegression")
        cls.module = propulsion.build_propulsion_module(cls.doc)

    @classmethod
    def tearDownClass(cls):
        App.closeDocument(cls.doc.Name)

    def test_rail_key_clears_complete_fixed_module_on_both_sides(self):
        from gondola.validation.propulsion import rail_key_access_check

        rows = rail_key_access_check(self.doc, self.module)
        self.assertEqual(
            {row["approach_side_y"] for row in rows},
            {1, -1},
        )
        for row in rows:
            self.assertTrue(row["passed"], row)
            for name in ("PortInputSupport", "StarboardDriverGear", "PortServo"):
                self.assertIn(name, row["checked_objects"])

    def test_closed_input_flange_blocks_key_even_when_fixed_frame_is_clear(self):
        from gondola.validation.propulsion import rail_key_access_check

        support = self.doc.PortInputSupport
        original = support.Shape.copy()
        try:
            obstruction = Part.makeBox(
                4, 2, 3, App.Vector(-10, 19, 5 - SELECTED_DRIVE.input_z_mm)
            )
            support.Shape = support.Shape.fuse(obstruction).removeSplitter()
            self.doc.recompute()
            rows = rail_key_access_check(self.doc, self.module)
            for row in rows:
                if row["approach_side_y"] > 0:
                    self.assertFalse(row["passed"], row)
                    self.assertEqual(
                        {hit["part"] for hit in row["collisions"]},
                        {"PortInputSupport"},
                    )
                else:
                    self.assertTrue(row["passed"], row)
        finally:
            support.Shape = original
            self.doc.recompute()

    def test_native_output_limits_ratio_and_fixed_input_datum(self):
        from gondola.validation.propulsion import (
            drive_motion_check,
            fixed_input_datum_check,
        )

        for prefix in ("Port", "Starboard"):
            with self.subTest(prefix=prefix):
                result = drive_motion_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)
                result = fixed_input_datum_check(self.doc, prefix)
                self.assertTrue(result["passed"], result)

    def test_wrong_input_rotation_direction_is_rejected(self):
        from gondola.validation.propulsion import drive_motion_check

        drive = self.doc.PortInputDrive
        expression = next(
            str(value)
            for path, value in drive.ExpressionEngine
            if str(path).endswith("Rotation.Angle")
        )
        try:
            drive.setExpression(
                "Placement.Rotation.Angle",
                f"PortPod.Placement.Rotation.Angle / {SELECTED_DRIVE.ratio:g}",
            )
            result = drive_motion_check(self.doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            drive.setExpression("Placement.Rotation.Angle", expression)
            self.doc.recompute()

    def test_real_tooth_outlines_clear_across_a_complete_tooth_phase(self):
        from gondola.validation.propulsion import gear_rotation_check

        for prefix in ("Port", "Starboard"):
            result = gear_rotation_check(self.doc, prefix)
            self.assertTrue(result["passed"], result)

    def test_all_output_and_input_bearings_are_captured(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import bearing_stack_check

        for prefix in ("Port", "Starboard"):
            for suffix in ("Negative", "Positive"):
                result = bearing_stack_check(
                    world_shape(self.doc.getObject(prefix + "OutputBearing" + suffix)),
                    world_shape(self.doc.getObject(prefix + "OutputShaft" + suffix)),
                    world_shape(self.module["frame"]),
                    world_shape(
                        self.doc.getObject(prefix + "OutputBearingCap" + suffix)
                    ),
                )
                self.assertTrue(result["passed"], (prefix, suffix, result))
            for suffix in ("Inner", "Outer"):
                result = bearing_stack_check(
                    world_shape(self.doc.getObject(prefix + "InputBearing" + suffix)),
                    world_shape(self.doc.getObject(prefix + "InputShaft")),
                    world_shape(self.doc.getObject(prefix + "InputSupport")),
                    world_shape(
                        self.doc.getObject(prefix + "InputBearingCap" + suffix)
                    ),
                )
                self.assertTrue(result["passed"], (prefix, suffix, result))

    def test_output_stubs_cannot_be_replaced_by_a_shaft_through_the_motor(self):
        from gondola.cad import world_shape
        from gondola.parts import propulsion
        from gondola.validation.propulsion import output_stub_check

        motor = world_shape(self.doc.PortMotor)
        pivot_y = self.doc.PortPod.getGlobalPlacement().Base.y
        for suffix in ("Negative", "Positive"):
            result = output_stub_check(
                world_shape(self.doc.getObject("PortOutputShaft" + suffix)),
                motor,
                pivot_y,
            )
            self.assertTrue(result["passed"], result)
        through_shaft = Part.makeCylinder(
            1.5,
            60,
            App.Vector(0, pivot_y - 30, propulsion.PIVOT_Z),
            App.Vector(0, 1, 0),
        )
        result = output_stub_check(through_shaft, motor, pivot_y)
        self.assertFalse(result["passed"])
        self.assertGreater(result["motor_overlap_mm3"], 0)

    def clamp_stack(self):
        from gondola.cad import world_shape

        return tuple(
            world_shape(self.doc.getObject(name))
            for name in (
                "PortMotorCarrier",
                "PortOutputClampPositiveBolt",
                "PortOutputClampPositiveNut",
            )
        )

    def test_split_clamp_has_seated_fasteners_and_full_nut_engagement(self):
        from gondola.validation.propulsion import clamp_fastener_check

        result = clamp_fastener_check(*self.clamp_stack())
        self.assertTrue(result["passed"], result)
        self.assertAlmostEqual(result["nut_engagement_length_mm"], 1.2)

    def test_servo_ear_fasteners_have_seated_heads_and_complete_smaller_nuts(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import clamp_fastener_check

        for prefix in ("Port", "Starboard"):
            clamp = Part.makeCompound(
                [
                    world_shape(self.doc.getObject(prefix + "Servo")),
                    world_shape(self.doc.getObject(prefix + "InputSupport")),
                ]
            )
            for suffix in ("Negative", "Positive"):
                result = clamp_fastener_check(
                    clamp,
                    world_shape(
                        self.doc.getObject(prefix + "ServoEar" + suffix + "Bolt")
                    ),
                    world_shape(
                        self.doc.getObject(prefix + "ServoEar" + suffix + "Nut")
                    ),
                    thread_diameter=1.6,
                    nut_height=1.3,
                )
                self.assertTrue(result["passed"], (prefix, suffix, result))
                self.assertAlmostEqual(result["nut_engagement_length_mm"], 1.3)

    def test_input_mounts_allow_bolt_first_removal_and_lateral_nut_exit(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import fastener_service_check

        objects = (
            self.module["printed"] + self.module["hardware"] + self.module["references"]
        )
        shapes = {obj.Name: world_shape(obj) for obj in objects}
        for prefix in ("Port", "Starboard"):
            for suffix in ("Negative", "Positive"):
                bolt_name = prefix + "InputMount" + suffix + "Bolt"
                nut_name = prefix + "InputMount" + suffix + "Nut"
                nut = shapes[nut_name]
                result = fastener_service_check(
                    shapes[bolt_name],
                    nut,
                    {
                        name: shape
                        for name, shape in shapes.items()
                        if name not in (bolt_name, nut_name)
                    },
                    nut_lateral_direction=(
                        1 if nut.BoundBox.Center.x > 0 else -1,
                        0,
                        0,
                    ),
                )
                self.assertTrue(result["passed"], (bolt_name, result))

    def test_outer_bearing_cap_nut_can_disengage_with_horn_clamp_installed(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import fastener_service_check

        objects = (
            self.module["printed"] + self.module["hardware"] + self.module["references"]
        )
        shapes = {obj.Name: world_shape(obj) for obj in objects}
        for prefix in ("Port", "Starboard"):
            bolt_name = prefix + "InputBearingCapOuterBolt"
            nut_name = prefix + "InputBearingCapOuterNut"
            result = fastener_service_check(
                shapes[bolt_name],
                shapes[nut_name],
                {
                    name: shape
                    for name, shape in shapes.items()
                    if name not in (bolt_name, nut_name)
                },
            )
            self.assertTrue(result["passed"], (bolt_name, result))
            self.assertAlmostEqual(result["nut_thread_disengagement_travel_mm"], 2.7)

    def test_unseated_clamp_nut_is_rejected(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import clamp_fastener_check

        clamp, bolt, nut = self.clamp_stack()
        result = clamp_fastener_check(clamp, bolt, translated_shape(nut, z=0.2))
        self.assertFalse(result["passed"], result)
        self.assertFalse(result["contacts"][1]["passed"])

    def test_bolt_must_cross_the_full_clamp_nut(self):
        from gondola.cad import translated_shape
        from gondola.validation.propulsion import clamp_fastener_check

        clamp, bolt, nut = self.clamp_stack()
        result = clamp_fastener_check(clamp, translated_shape(bolt, z=-2), nut)
        self.assertFalse(result["passed"], result)
        self.assertGreater(result["missing_bolt_thread_core_mm3"], 0)

    def test_bought_gears_bearings_and_shafts_are_never_print_parts(self):
        hardware = self.module["hardware"]
        self.assertEqual(sum(obj.HardwareSKU == "MR63ZZ" for obj in hardware), 8)
        self.assertEqual(
            sum(str(obj.HardwareSKU).startswith("GEABP") for obj in hardware), 4
        )
        self.assertEqual(
            sum(str(obj.HardwareSKU).startswith("PSFU") for obj in hardware), 6
        )
        self.assertTrue(
            all(not bool(getattr(obj, "PrintPart", False)) for obj in hardware)
        )
        self.assertTrue(
            all(len(obj.Shape.Solids) == 1 for obj in self.module["printed"])
        )


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class InterchangeableGearDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gondola.parts import propulsion

        cls.configurations = {}
        for key, configuration in DRIVE_CONFIGURATIONS.items():
            doc = App.newDocument("InterchangeableDrive" + key)
            cls.configurations[key] = (
                doc,
                propulsion.build_propulsion_module(doc, drive=configuration),
            )

    @classmethod
    def tearDownClass(cls):
        for doc, _ in cls.configurations.values():
            App.closeDocument(doc.Name)

    def test_gear_substitution_only_replaces_drivers_and_matched_input_supports(self):
        from gondola.print_export import geometry_comparison

        _, first = self.configurations["60_20"]
        _, second = self.configurations["64_20"]
        for category in ("printed", "hardware", "references"):
            first_parts = {obj.Name: obj for obj in first[category]}
            second_parts = {obj.Name: obj for obj in second[category]}
            self.assertEqual(set(first_parts), set(second_parts))
            for name, original in first_parts.items():
                replacement = second_parts[name]
                if name.endswith("DriverGear"):
                    self.assertEqual(original.HardwareSKU, "GEABP0.5-60-3-B-3")
                    self.assertEqual(replacement.HardwareSKU, "GEABP0.5-64-3-B-3")
                    self.assertGreater(replacement.Shape.Volume, original.Shape.Volume)
                    continue
                if name.endswith("InputSupport"):
                    self.assertEqual(original.PrintSKU, "GearedInputSupport60T")
                    self.assertEqual(replacement.PrintSKU, "GearedInputSupport64T")
                    result = geometry_comparison(original.Shape, replacement.Shape)
                    self.assertGreater(result["difference_mm3"], 1)
                    continue
                with self.subTest(category=category, part=name):
                    result = geometry_comparison(original.Shape, replacement.Shape)
                    self.assertTrue(
                        all(
                            result[field] < 1e-5
                            for field in (
                                "difference_mm3",
                                "bounds_difference_mm",
                                "volume_difference_mm3",
                            )
                        ),
                        result,
                    )
                    self.assertEqual(
                        getattr(original, "HardwareSKU", None),
                        getattr(replacement, "HardwareSKU", None),
                    )

    def test_native_motion_teeth_and_mounts_follow_each_complete_configuration(self):
        from gondola.validation.propulsion import (
            drive_motion_check,
            fixed_input_datum_check,
            fixed_input_mount_check,
            rail_key_access_check,
        )

        for key, (doc, module) in self.configurations.items():
            configuration = DRIVE_CONFIGURATIONS[key]
            for prefix in ("Port", "Starboard"):
                with self.subTest(configuration=key, pod=prefix):
                    motion = drive_motion_check(doc, prefix)
                    self.assertTrue(motion["passed"], motion)
                    for case in motion["cases"]:
                        self.assertAlmostEqual(
                            case["required_servo_deg"],
                            -case["bounded_output_deg"] / configuration.ratio,
                        )
                    for check in (fixed_input_datum_check, fixed_input_mount_check):
                        result = check(doc, prefix)
                        self.assertTrue(result["passed"], result)
            for row in rail_key_access_check(doc, module):
                self.assertTrue(row["passed"], (key, row))

    def test_both_horn_clamp_halves_have_continuous_service_paths_for_each_gear_pair(
        self,
    ):
        from gondola.validation.propulsion import horn_clamp_service_check

        for key, (doc, module) in self.configurations.items():
            for prefix in ("Port", "Starboard"):
                with self.subTest(configuration=key, pod=prefix):
                    rows = horn_clamp_service_check(doc, module, prefix)
                    self.assertEqual(
                        {row["part"] for row in rows},
                        {prefix + "HornClampUpper", prefix + "HornClampLower"},
                    )
                    for row in rows:
                        self.assertTrue(row["passed"], row)
                        self.assertTrue(all(step["passed"] for step in row["segments"]))
                    lower = next(row for row in rows if row["part"].endswith("Lower"))
                    self.assertIn(
                        prefix + "InputSupport", lower["segments"][1]["obstacles"]
                    )
                    self.assertIn(
                        prefix + "ServoHorn", lower["segments"][1]["obstacles"]
                    )
                    self.assertIn(
                        prefix + "HornClampUpper", lower["removed_local_parts"]
                    )

    def test_correct_direction_with_stale_ratio_is_rejected_for_alternate_gears(self):
        from gondola.validation.propulsion import drive_motion_check

        doc, _ = self.configurations["64_20"]
        drive = doc.PortInputDrive
        expression = next(
            str(value)
            for path, value in drive.ExpressionEngine
            if str(path).endswith("Rotation.Angle")
        )
        try:
            drive.setExpression(
                "Placement.Rotation.Angle", "-PortPod.Placement.Rotation.Angle / 3"
            )
            result = drive_motion_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            drive.setExpression("Placement.Rotation.Angle", expression)
            doc.recompute()

    def test_saved_contract_is_not_a_live_ratio_override(self):
        from gondola.contracts.drive import drive_for_document
        from gondola.validation.baseline import native_interface_metadata

        doc, _ = self.configurations["60_20"]
        module = doc.MainPropulsionModule
        original = module.DriveContract
        metadata = native_interface_metadata(doc)
        self.assertEqual(metadata[module.Name]["GearConfiguration"], "60_20")
        try:
            altered = json.loads(original)
            altered["angle_ratio"] = -3.2
            module.DriveContract = json.dumps(altered)
            self.assertNotEqual(native_interface_metadata(doc), metadata)
            with self.assertRaisesRegex(ValueError, "differs"):
                drive_for_document(doc)
        finally:
            module.DriveContract = original

    def test_larger_gear_requires_verified_removal_before_outer_cap_bolt_service(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import (
            _record_fastener_checks,
            fastener_service_check,
        )

        doc, module = self.configurations["64_20"]
        objects = module["printed"] + module["hardware"] + module["references"]
        physical = {obj.Name: world_shape(obj) for obj in objects}
        bolt_name = "PortInputBearingCapOuterBolt"
        nut_name = "PortInputBearingCapOuterNut"
        gear_name = "PortDriverGear"
        unprepared = fastener_service_check(
            physical[bolt_name],
            physical[nut_name],
            {
                name: shape
                for name, shape in physical.items()
                if name not in (bolt_name, nut_name)
            },
        )
        self.assertFalse(unprepared["passed"], unprepared)
        self.assertGreater(
            unprepared["bolt_axial_withdrawal"]["segments"][0]["intersection_mm3"][
                gear_name
            ],
            1,
        )

        # Check the recorded ordering independently from the upstream geometric
        # path audits, whose real results are required by the full validation.
        report = {
            "fastener_stacks": [],
            "fastener_service": [],
            "input_cartridge_removal": [
                {"cartridge": "PortInputCartridge", "passed": True}
            ],
            "gear_service": [{"gear": gear_name, "passed": True}],
        }
        one_fastener = {**module, "hardware": [doc.getObject(bolt_name)]}
        _record_fastener_checks(report, doc, one_fastener, objects, physical)
        result = report["fastener_service"][-1]
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["service_group"], "PortInputCartridge")
        self.assertIn(gear_name, result["removed_local_parts"])
        self.assertNotIn(gear_name, result["retained_service_parts"])
        self.assertIn("PortHornClampUpper", result["retained_service_parts"])
        self.assertEqual(
            {row["object"] for row in result["service_dependencies"]},
            {"PortInputCartridge", gear_name},
        )
        report["gear_service"][0]["passed"] = False
        _record_fastener_checks(report, doc, one_fastener, objects, physical)
        self.assertFalse(report["fastener_service"][-1]["passed"])

    def test_shifted_or_rotated_input_cartridge_is_rejected(self):
        from gondola.validation.propulsion import fixed_input_datum_check

        for key, (doc, _) in self.configurations.items():
            cartridge = doc.PortInputCartridge
            original = App.Placement(cartridge.Placement)
            try:
                with self.subTest(configuration=key, change="position"):
                    cartridge.Placement.Base = original.Base + App.Vector(0.02, 0, 0)
                    doc.recompute()
                    result = fixed_input_datum_check(doc, "Port")
                    self.assertFalse(result["passed"], result)
                with self.subTest(configuration=key, change="rotation"):
                    cartridge.Placement = App.Placement(
                        original.Base, App.Rotation(App.Vector(0, 1, 0), 0.1)
                    )
                    doc.recompute()
                    result = fixed_input_datum_check(doc, "Port")
                    self.assertFalse(result["passed"], result)
            finally:
                cartridge.Placement = original
                doc.recompute()

    def test_stale_adjustment_property_or_live_datum_expression_is_rejected(self):
        from gondola.validation.propulsion import fixed_input_datum_check

        doc, _ = self.configurations["60_20"]
        cartridge = doc.PortInputCartridge
        try:
            cartridge.addProperty("App::PropertyLength", "MeshClearance")
            result = fixed_input_datum_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            cartridge.removeProperty("MeshClearance")
        try:
            # A currently correct expression would allow future drift.
            cartridge.setExpression("Placement.Base.x", "8 mm")
            doc.recompute()
            result = fixed_input_datum_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            cartridge.setExpression("Placement.Base.x", None)
            doc.recompute()

    def test_wrong_support_identity_is_rejected(self):
        from gondola.validation.propulsion import fixed_input_datum_check

        doc, _ = self.configurations["64_20"]
        support = doc.PortInputSupport
        original = support.PrintSKU
        try:
            support.PrintSKU = "GearedInputSupport60T"
            result = fixed_input_datum_check(doc, "Port")
            self.assertFalse(result["passed"], result)
        finally:
            support.PrintSKU = original

    def test_wrong_gear_specific_support_and_enlarged_mount_holes_are_rejected(self):
        from gondola.validation.propulsion import fixed_input_mount_check

        baseline, _ = self.configurations["60_20"]
        doc, _ = self.configurations["64_20"]
        support = doc.PortInputSupport
        original = support.Shape.copy()
        try:
            support.Shape = baseline.PortInputSupport.Shape.copy()
            doc.recompute()
            result = fixed_input_mount_check(doc, "Port")
            self.assertFalse(result["passed"], result)
            support.Shape = original
            # A radial slot can retain nominal bolt contact while permitting
            # movement. Removing any of the round bore's rim must be rejected.
            cutter = Part.makeCylinder(
                1.3, 3, App.Vector(-4.5, 18.5, 8.3), App.Vector(0, 1, 0)
            )
            cutter.Placement = (
                support.getGlobalPlacement().inverse().multiply(cutter.Placement)
            )
            support.Shape = original.cut(cutter)
            doc.recompute()
            result = fixed_input_mount_check(doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertGreater(
                result["cases"][0]["round_mount_holes"][1][
                    "missing_round_hole_rim_mm3"
                ],
                0.1,
            )
        finally:
            support.Shape = original
            doc.recompute()

    def test_fixed_mount_checks_follow_the_whole_module_placement(self):
        from gondola.validation.propulsion import fixed_input_mount_check

        doc, _ = self.configurations["64_20"]
        module = doc.MainPropulsionModule
        original = App.Placement(module.Placement)
        try:
            module.Placement = App.Placement(
                App.Vector(36, 0.45, 2), App.Rotation(App.Vector(0, 0, 1), 13)
            )
            doc.recompute()
            for prefix in ("Port", "Starboard"):
                result = fixed_input_mount_check(doc, prefix)
                self.assertTrue(result["passed"], result)
        finally:
            module.Placement = original
            doc.recompute()

    def test_fixed_support_collision_is_rejected_even_with_seated_bolts(self):
        from gondola.cad import world_shape
        from gondola.validation.propulsion import fixed_input_mount_check

        doc, _ = self.configurations["64_20"]
        frame = doc.PropulsionFixedFrame
        original = frame.Shape.copy()
        try:
            frame.Shape = original.fuse(world_shape(doc.PortInputSupport))
            doc.recompute()
            result = fixed_input_mount_check(doc, "Port")
            self.assertFalse(result["passed"], result)
            self.assertTrue(
                any(
                    row["support_frame_intersection_mm3"] > 1 for row in result["cases"]
                )
            )
        finally:
            frame.Shape = original
            doc.recompute()


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class SavedDriveManufacturingTests(unittest.TestCase):
    def test_wall_probes_follow_saved_alternative_not_source_default(self):
        from gondola.parts import equipment_mounts, optical_mount, propulsion, rail
        from gondola.validation.manufacturing import review

        alternative = next(
            drive for drive in DRIVE_CONFIGURATIONS.values() if drive != SELECTED_DRIVE
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alternative_drive.FCStd"
            doc = App.newDocument("SavedAlternativeDriveWalls")
            try:
                propulsion.build_propulsion_module(doc, drive=alternative)
                # A nonzero module placement also exercises the measurement's
                # conversion from global coordinates back to the module frame.
                doc.MainPropulsionModule.Placement.Base = App.Vector(36, 0.45, 0)
                rail.build_rail(doc)
                host = doc.addObject("App::Part", "BatteryEquipmentModule")
                equipment_mounts.build_mount(doc, host, "battery")
                optical_mount.build_optical_mount(doc, host)
                doc.recompute()
                doc.saveAs(str(path))
            finally:
                App.closeDocument(doc.Name)

            saved = App.openDocument(str(path), hidden=True)
            try:
                saved.recompute()
                registry = SimpleNamespace(
                    PrintedParts=[saved.PortInputSupport],
                    RailSegments=[saved.ContinuousRail],
                )
                result = review(saved, registry)
                measurements = {
                    row["feature"]: row for row in result["actual_feature_measurements"]
                }
                for feature, _, start, end, _ in propulsion.manufacturing_wall_probes(
                    drive=alternative
                ):
                    with self.subTest(feature=feature):
                        row = measurements[feature]
                        self.assertEqual(row["sample_line_mm"], [start, end])
                        self.assertTrue(row["passed"], row)
                self.assertTrue(result["passed"], result)
            finally:
                App.closeDocument(saved.Name)


if __name__ == "__main__":
    unittest.main()
