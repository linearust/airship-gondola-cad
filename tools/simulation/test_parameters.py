"""Read-only geometry export and force-datum checks; run in FreeCAD Python."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import FreeCAD as App
import Part

from gondola.cad import world_shape
from gondola.config import BASELINE_FILE
from gondola.provenance import file_sha256
from tools.simulation.export_parameters import (
    export,
    extract,
    input_support_geometry,
    instrument_pitch_degrees,
    optical_attachment_geometry,
    output_support_geometry,
    printed_carrier_mass_properties,
    vector_m,
)


class UnitTests(unittest.TestCase):
    def test_si_conversion(self):
        self.assertEqual(vector_m((0, -74.9, 50)), [0, -0.0749, 0.05])

    def test_uniform_print_mass_and_centroid_inertia_have_correct_si_units(self):
        cube = Part.makeBox(10, 10, 10, App.Vector(5, -5, -5))
        result = printed_carrier_mass_properties(cube)
        self.assertAlmostEqual(result["mass_kg"], 0.00101)
        self.assertEqual(result["centre_from_tilt_axis_neutral_m"], [0.01, 0, 0])
        tensor = result["inertia_about_print_cg_neutral_kg_m2"]
        for row in range(3):
            for column in range(3):
                self.assertAlmostEqual(
                    tensor[row][column],
                    0.00101 * 0.01**2 / 6 if row == column else 0,
                    places=14,
                )
        self.assertEqual(
            printed_carrier_mass_properties(Part.makeCompound([cube])), result
        )
        with self.assertRaisesRegex(ValueError, "exactly one solid"):
            printed_carrier_mass_properties(
                Part.makeCompound(
                    [cube, Part.makeBox(10, 10, 10, App.Vector(25, -5, -5))]
                )
            )


class SupportTopologyTests(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("SimulationSupportTopology")
        self.addCleanup(App.closeDocument, self.doc.Name)
        root = self.doc.addObject("App::Part", "MainPropulsionModule")
        root.Placement.Base.x = 14
        frame = self.doc.addObject("Part::Feature", "PropulsionFixedFrame")
        root.addObject(frame)
        for prefix, sign, shaft_suffix in (
            ("Port", 1, "Negative"),
            ("Starboard", -1, "Positive"),
        ):
            assembly = self.doc.addObject("App::Part", prefix + "Assembly")
            root.addObject(assembly)
            pod = self.doc.addObject("App::Part", prefix + "Pod")
            assembly.addObject(pod)
            pod.Placement.Base = App.Vector(0, sign * 75, 50)
            for label, y in (("Inboard", 28), ("Outboard", 41)):
                obj = self.doc.addObject(
                    "Part::Feature", prefix + "OutputBearing" + label
                )
                assembly.addObject(obj)
                obj.Shape = Part.makeCylinder(
                    3, 2.5, App.Vector(0, -1.25, 0), App.Vector(0, 1, 0)
                ).cut(
                    Part.makeCylinder(
                        1.5, 2.5, App.Vector(0, -1.25, 0), App.Vector(0, 1, 0)
                    )
                )
                obj.Placement.Base = App.Vector(0, sign * y, 50)
                obj.addProperty("App::PropertyString", "HardwareSKU")
                obj.HardwareSKU = "BEARING_3X6X2_5"
            cap = self.doc.addObject("Part::Feature", prefix + "BearingCap")
            assembly.addObject(cap)
            shaft = self.doc.addObject(
                "Part::Feature", prefix + "OutputShaft" + shaft_suffix
            )
            pod.addObject(shaft)
            drive = self.doc.addObject("App::Part", prefix + "InputDrive")
            root.addObject(drive)
            drive.Placement.Base = App.Vector(sign * 16, -sign * 8, 50)
            input_bearing = self.doc.addObject("Part::Feature", prefix + "InputBearing")
            assembly.addObject(input_bearing)
            input_bearing.Shape = obj.Shape.copy()
            input_bearing.Placement.Base = App.Vector(sign * 16, sign * 33, 50)
            input_bearing.addProperty("App::PropertyString", "HardwareSKU")
            input_bearing.HardwareSKU = "BEARING_3X6X2_5"
            input_shaft = self.doc.addObject("Part::Feature", prefix + "InputShaft")
            drive.addObject(input_shaft)
            input_shaft.Shape = Part.makeCylinder(
                1.5, 35, App.Vector(0, sign * 14.5, 0), App.Vector(0, sign, 0)
            ).cut(
                Part.makeBox(2, 16, 4, App.Vector(1, 14.5 if sign > 0 else -30.5, -2))
            )
            input_shaft.addProperty("App::PropertyString", "HardwareSKU")
            input_shaft.HardwareSKU = "SS304_CUT3_L35_FLAT16_A0"
        self.doc.recompute()

    def test_input_bearing_stays_fixed_and_does_not_become_a_third_output_bearing(self):
        for prefix, sign in (("Port", 1), ("Starboard", -1)):
            output = output_support_geometry(self.doc, prefix)
            self.assertEqual(set(output["bearings"]), {"Inboard", "Outboard"})
            support = input_support_geometry(self.doc, prefix)
            self.assertEqual(support["shared_bearing_cap"], prefix + "BearingCap")
            bearing = support["bearing"]
            self.assertEqual(bearing["object"], prefix + "InputBearing")
            self.assertEqual(
                bearing["centre_cad_m"],
                [0.030 if sign > 0 else -0.002, sign * 0.033, 0.05],
            )
            self.assertEqual(
                bearing["centre_from_input_axis_neutral_m"], [0, sign * 0.041, 0]
            )
            self.assertTrue(bearing["fixed_during_tilt"])
            self.assertEqual(support["input_shaft"]["length_m"], 0.035)
            self.assertEqual(support["input_shaft"]["proximal_flat_length_m"], 0.016)
            self.assertLess(support["input_shaft"]["round_journal_missing_mm3"], 1e-7)

    def test_input_bearing_cannot_rotate_with_input_or_output(self):
        bearing = self.doc.PortInputBearing
        parent = bearing.getParentGeoFeatureGroup()
        for group in (self.doc.PortInputDrive, self.doc.PortPod):
            with self.subTest(group=group.Name):
                try:
                    group.addObject(bearing)
                    with self.assertRaisesRegex(ValueError, "Input support topology"):
                        input_support_geometry(self.doc, "Port")
                finally:
                    parent.addObject(bearing)

    def test_input_support_rejects_lost_journal_or_misaligned_bearing(self):
        bearing, shaft = self.doc.PortInputBearing, self.doc.PortInputShaft
        original_bearing = App.Placement(bearing.Placement)
        original_shaft = shaft.Shape.copy()
        try:
            bearing.Placement.Base.x += 1
            with self.assertRaisesRegex(ValueError, "coaxial"):
                input_support_geometry(self.doc, "Port")
            bearing.Placement = original_bearing
            shaft.Shape = original_shaft.cut(
                Part.makeBox(2, 35, 4, App.Vector(1, 14.5, -2))
            )
            with self.assertRaisesRegex(ValueError, "round bearing journal"):
                input_support_geometry(self.doc, "Port")
        finally:
            bearing.Placement = original_bearing
            shaft.Shape = original_shaft

    def test_literal_inboard_pair_and_only_driven_shaft_are_exported(self):
        for prefix, sign, shaft_suffix in (
            ("Port", 1, "Negative"),
            ("Starboard", -1, "Positive"),
        ):
            with self.subTest(side=prefix):
                support = output_support_geometry(self.doc, prefix)
                self.assertEqual(
                    support["integrated_fixed_frame"], "PropulsionFixedFrame"
                )
                self.assertEqual(support["fixed_bearing_cap"], prefix + "BearingCap")
                self.assertEqual(
                    support["output_shaft"],
                    {
                        "object": prefix + "OutputShaft" + shaft_suffix,
                        "rotating_parent": prefix + "Pod",
                    },
                )
                self.assertEqual(support["idler_shafts"], [])
                self.assertAlmostEqual(support["bearing_centre_spacing_m"], 0.013)
                for label, position, offset in (
                    ("Inboard", 0.028, -0.047),
                    ("Outboard", 0.041, -0.034),
                ):
                    bearing = support["bearings"][label]
                    self.assertEqual(
                        bearing["centre_cad_m"], [0.014, sign * position, 0.05]
                    )
                    self.assertEqual(
                        bearing["centre_from_tilt_axis_neutral_m"],
                        [0, sign * offset, 0],
                    )
                    self.assertTrue(bearing["fixed_during_tilt"])

    def test_fixed_parts_cannot_move_with_the_rotor(self):
        for name in (
            "PortOutputBearingInboard",
            "PortBearingCap",
            "PropulsionFixedFrame",
        ):
            with self.subTest(part=name):
                obj = self.doc.getObject(name)
                parent = obj.getParentGeoFeatureGroup()
                try:
                    self.doc.PortPod.addObject(obj)
                    with self.assertRaisesRegex(ValueError, "topology changed"):
                        output_support_geometry(self.doc, "Port")
                finally:
                    parent.addObject(obj)

    def test_common_global_transform_preserves_relative_support_geometry(self):
        expected = output_support_geometry(self.doc, "Port")
        expected_input = input_support_geometry(self.doc, "Port")
        self.doc.MainPropulsionModule.Placement = App.Placement(
            App.Vector(71, -39, 26), App.Rotation(App.Vector(2, -3, 5), 37)
        )
        self.doc.recompute()
        actual = output_support_geometry(self.doc, "Port")
        actual_input = input_support_geometry(self.doc, "Port")
        self.assertEqual(
            actual_input["bearing"]["centre_from_input_axis_neutral_m"],
            expected_input["bearing"]["centre_from_input_axis_neutral_m"],
        )
        self.assertNotEqual(
            actual_input["bearing"]["centre_cad_m"],
            expected_input["bearing"]["centre_cad_m"],
        )
        self.assertAlmostEqual(actual["bearing_centre_spacing_m"], 0.013)
        for label in ("Inboard", "Outboard"):
            self.assertEqual(
                actual["bearings"][label]["centre_from_tilt_axis_neutral_m"],
                expected["bearings"][label]["centre_from_tilt_axis_neutral_m"],
            )
            self.assertNotEqual(
                actual["bearings"][label]["centre_cad_m"],
                expected["bearings"][label]["centre_cad_m"],
            )

    def test_outboard_or_noncoaxial_bearing_cannot_claim_inboard_support(self):
        bearing = self.doc.PortOutputBearingOutboard
        for point in (
            App.Vector(0, 80, 50),
            App.Vector(1, 41, 50),
            App.Vector(0, 41, 51),
        ):
            with self.subTest(position=point):
                bearing.Placement.Base = point
                with self.assertRaisesRegex(ValueError, "coaxial and inboard"):
                    output_support_geometry(self.doc, "Port")

    def test_extra_bearing_or_returned_idler_and_saddle_are_rejected(self):
        for name in (
            "PortOutputShaftPositive",
            "ServoDriveBridge",
            "PortUnexpectedBearing",
        ):
            with self.subTest(part=name):
                obj = self.doc.addObject("Part::Feature", name)
                if name.endswith("Bearing"):
                    obj.addProperty("App::PropertyString", "HardwareSKU")
                    obj.HardwareSKU = "BEARING_3X6X2_5"
                try:
                    with self.assertRaisesRegex(ValueError, "topology changed"):
                        output_support_geometry(self.doc, "Port")
                finally:
                    self.doc.removeObject(obj.Name)


class NativeSupportExportTests(unittest.TestCase):
    def test_built_and_reopened_input_support_stays_separate_from_output_pair(self):
        from gondola.parts import propulsion

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input_support.FCStd"
            doc = App.newDocument("NativeInputSupportExport")
            try:
                propulsion.build_propulsion_module(doc)
                doc.recompute()
                before = {
                    prefix: input_support_geometry(doc, prefix)
                    for prefix in ("Port", "Starboard")
                }
                doc.saveAs(str(path))
            finally:
                App.closeDocument(doc.Name)
            doc = App.openDocument(str(path), hidden=True)
            try:
                for prefix, sign in (("Port", 1), ("Starboard", -1)):
                    with self.subTest(side=prefix):
                        result = input_support_geometry(doc, prefix)
                        self.assertEqual(result, before[prefix])
                        self.assertEqual(
                            result["bearing"]["centre_cad_m"],
                            [sign * 0.016, sign * 0.033, 0.05],
                        )
                        self.assertEqual(result["input_shaft"]["length_m"], 0.035)
                        self.assertEqual(
                            result["input_shaft"]["round_journal_missing_mm3"], 0
                        )
                        output = output_support_geometry(doc, prefix)
                        self.assertEqual(
                            set(output["bearings"]), {"Inboard", "Outboard"}
                        )
                        self.assertAlmostEqual(
                            output["bearing_centre_spacing_m"], 0.013
                        )
            finally:
                App.closeDocument(doc.Name)


class OpticalAttachmentTests(unittest.TestCase):
    def native_optical(self):
        from gondola.parts import instrument_mount, optical_mount, optical_sensor

        doc = App.newDocument("SimulationOpticalAttachment")
        self.addCleanup(
            lambda name=doc.Name: (
                App.closeDocument(name) if name in App.listDocuments() else None
            )
        )
        module = doc.addObject("App::Part", "ElectronicsEquipmentModule")
        module.Placement = App.Placement(
            App.Vector(-56, 0, 0), App.Rotation(App.Vector(0, 0, 1), 180)
        )
        kit = instrument_mount.build_mount(doc, module)
        optical = optical_mount.build_optical_mount(doc, kit["pitch_stage"])
        optical_sensor.build_sensor(doc, optical["sensor_frame"])
        fc = doc.addObject("Part::Feature", "ModuleFCEnvelope")
        kit["pitch_stage"].addObject(fc)
        fc.Shape = Part.makeBox(4, 4, 4, App.Vector(-2, -2, 27))
        doc.recompute()
        return doc

    def test_saved_native_common_platform_exports_fixed_optical_and_shared_pivot(self):
        doc = self.native_optical()
        result = optical_attachment_geometry(doc)
        self.assertEqual(result["optical_attachment_mode"], "instrument")
        self.assertEqual(result["optical_adjustment_degrees_of_freedom"], 0)
        self.assertEqual(result["instrument_adjustment_degrees_of_freedom"], 1)
        self.assertEqual(result["optical_native_parent"], "InstrumentPitchStage")
        self.assertEqual(result["optical_module_origin_cad_m"], [-0.056, 0, 0.0195])
        self.assertEqual(
            result["optical_sensor_frame_origin_cad_m"],
            result["optical_module_origin_cad_m"],
        )
        self.assertEqual(result["instrument_pitch_pivot_cad_m"], [-0.056, 0, 0.0275])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "optical.FCStd"
            doc.saveAs(str(path))
            App.closeDocument(doc.Name)
            reopened = App.openDocument(str(path), hidden=True)
            try:
                self.assertEqual(optical_attachment_geometry(reopened), result)
            finally:
                App.closeDocument(reopened.Name)

    def test_fc_and_mtf_follow_exact_same_rigid_matrix_at_all_review_poses(self):
        from gondola.parts.instrument_mount import set_pitch

        doc = self.native_optical()
        module_pose = App.Placement(
            App.Vector(71, -39, 26), App.Rotation(App.Vector(2, -3, 5), 37)
        )
        doc.ElectronicsEquipmentModule.Placement = module_pose
        relative = (
            doc.ModuleFCEnvelope.getGlobalPlacement()
            .inverse()
            .multiply(doc.ModuleMTF02PEnvelope.getGlobalPlacement())
        )
        for angle in (-20, -10, 0, 10, 20):
            set_pitch(doc, angle)
            theta = math.radians(angle)
            stage = App.Placement(
                App.Vector(-8 * math.sin(theta), 0, 27.5 - 8 * math.cos(theta)),
                App.Rotation(App.Vector(0, 1, 0), angle),
            )
            for obj, local in (
                (doc.ModuleFCEnvelope, App.Placement()),
                (
                    doc.ModuleMTF02PEnvelope,
                    App.Placement(),
                ),
            ):
                expected = module_pose.multiply(stage).multiply(local)
                self.assertTrue(
                    obj.getGlobalPlacement().isSame(expected, 1e-7), obj.Name
                )
            self.assertTrue(
                doc.ModuleFCEnvelope.getGlobalPlacement()
                .inverse()
                .multiply(doc.ModuleMTF02PEnvelope.getGlobalPlacement())
                .isSame(relative, 1e-7)
            )
            self.assertEqual(
                optical_attachment_geometry(doc)["instrument_pitch_pivot_cad_m"],
                vector_m(module_pose.multVec(App.Vector(0, 0, 27.5))),
            )

    def test_detached_fc_bracket_or_sensor_frame_cannot_claim_common_motion(self):
        doc = self.native_optical()
        for obj in (
            doc.OpticalFlowModule,
            doc.ModuleFCEnvelope,
            doc.OpticalSensorFrame,
            doc.ElectronicsMount,
        ):
            parent = obj.getParentGeoFeatureGroup()
            try:
                doc.ElectronicsEquipmentModule.addObject(obj)
                with self.assertRaisesRegex(ValueError, "hierarchy"):
                    optical_attachment_geometry(doc)
            finally:
                parent.addObject(obj)

    def test_legacy_modes_controls_and_independent_joint_are_rejected(self):
        doc = self.native_optical()
        optical = doc.OpticalFlowModule
        for mode in ("carrier", "rail", ""):
            optical.OpticalAttachmentMode = mode
            with self.assertRaisesRegex(ValueError, "attachment|legacy"):
                optical_attachment_geometry(doc)
        optical.OpticalAttachmentMode = "instrument"
        for name in ("RailPositionX", "CarrierHostName", "MountSide"):
            optical.addProperty("App::PropertyString", name)
            with self.assertRaisesRegex(ValueError, "attachment|legacy"):
                optical_attachment_geometry(doc)
            optical.removeProperty(name)
        doc.addObject("App::Part", "OpticalPitchStage")
        with self.assertRaisesRegex(ValueError, "hierarchy|legacy"):
            optical_attachment_geometry(doc)

    def test_shifted_fixed_frames_or_hinge_pivot_are_rejected(self):
        doc = self.native_optical()
        for obj, message in (
            (doc.OpticalFlowModule, "frame datum"),
            (doc.OpticalSensorFrame, "fixed"),
        ):
            original = App.Placement(obj.Placement)
            obj.Placement.Base.z += 0.1
            with self.assertRaisesRegex(ValueError, message):
                optical_attachment_geometry(doc)
            obj.Placement = original
        doc.InstrumentPitchStage.setExpression("Placement.Base.z", None)
        doc.InstrumentPitchStage.Placement.Base.z += 0.1
        with self.assertRaisesRegex(ValueError, "pivot datum"):
            optical_attachment_geometry(doc)

    def test_pose_reader_retains_clamped_command_and_checks_actual_rotation(self):
        from gondola.parts.instrument_mount import set_pitch

        doc = self.native_optical()
        stage = doc.InstrumentPitchStage
        for command, expected in ((-999, -20), (-11, -11), (0, 0), (999, 20)):
            set_pitch(doc, command)
            before = App.Placement(stage.Placement)
            stored_command = float(
                stage.Pitch
            )  # FreeCAD angle properties cap at +/-360.
            self.assertEqual(instrument_pitch_degrees(stage), expected)
            self.assertEqual(float(stage.Pitch), stored_command)
            self.assertTrue(stage.Placement.isSame(before, 1e-10))
        stage.setExpression("Placement.Rotation.Angle", None)
        stage.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 3)
        with self.assertRaisesRegex(ValueError, "pure local-Y"):
            instrument_pitch_degrees(stage)


class SavedGeometryTests(unittest.TestCase):
    def setUp(self):
        self.digest = file_sha256(BASELINE_FILE)
        self.doc = App.openDocument(str(BASELINE_FILE))
        self.doc_name = self.doc.Name

    def tearDown(self):
        if self.doc_name in App.listDocuments():
            App.closeDocument(self.doc_name)
        self.assertEqual(file_sha256(BASELINE_FILE), self.digest)

    def test_snapshot_uses_complete_parent_placement(self):
        result = extract(self.doc)
        geo = result["exact_geometry"]
        self.assertNotIn("simplified_geometry", result)
        self.assertAlmostEqual(geo["main_pivot_span_m"], 0.150)
        self.assertEqual(geo["pivot_height_from_rail_contact_m"], 0.050)
        self.assertEqual(
            geo["main_propulsors"]["Port"]["pivot_cad_m"], [0.014, 0.075, 0.050]
        )
        self.assertEqual(
            geo["main_propulsors"]["Starboard"]["pivot_cad_m"], [0.014, -0.075, 0.050]
        )
        frame = geo["propulsion_reference_frame"]
        self.assertEqual(frame["origin_cad_m"], [0.014, 0, 0])
        self.assertEqual(
            frame["pivot_positions_m"],
            {"Port": [0, 0.075, 0.05], "Starboard": [0, -0.075, 0.05]},
        )
        self.assertEqual(geo["instrument_pitch_pivot_cad_m"], [-0.082, 0, 0.0275])
        self.assertEqual(geo["optical_attachment_mode"], "instrument")
        self.assertEqual(geo["optical_adjustment_degrees_of_freedom"], 0)
        self.assertEqual(geo["instrument_adjustment_degrees_of_freedom"], 1)
        self.assertEqual(geo["optical_native_parent"], "InstrumentPitchStage")
        self.assertNotIn("OpticalFlowModule", geo["module_origins_cad_m"])
        self.assertEqual(geo["servo_to_output_angle_ratio"], -3)
        for name in ("Port", "Starboard"):
            pod = self.doc.getObject(name + "Pod")
            self.assertEqual(
                vector_m(pod.getGlobalPlacement().multVec(App.Vector(-0.6, 0, 0))),
                geo["main_propulsors"][name]["motor_envelope_centre_cad_m"],
            )
            self.assertEqual(
                vector_m(pod.getGlobalPlacement().multVec(App.Vector(-5, 0, 0))),
                geo["main_propulsors"][name]["motor_mount_face_cad_m"],
            )
            rotor = result["rotating_assembly_analysis"][name]
            support = rotor["support_geometry"]
            self.assertEqual(
                support["arrangement"], "two_fixed_inboard_bearings_open_outer_side"
            )
            self.assertAlmostEqual(support["bearing_centre_spacing_m"], 0.013)
            self.assertEqual(support["idler_shafts"], [])
            input_support = result["input_drive_support_geometry"][name]
            self.assertEqual(input_support["bearing"]["object"], name + "InputBearing")
            self.assertTrue(input_support["bearing"]["fixed_during_tilt"])
            self.assertEqual(input_support["input_shaft"]["length_m"], 0.035)
            self.assertEqual(
                vector_m(pod.getGlobalPlacement().multVec(App.Vector(6.3, 0, 0))),
                rotor["illustrative_propeller_disk_centre_cad_m"],
            )
            for key in (
                "actual_hub_seating_offset_m",
                "actual_hub_midplane_cad_m",
                "actual_blade_axial_envelope_m",
                "installed_rotating_mass_kg",
                "installed_rotating_cg_from_tilt_axis_neutral_m",
                "installed_rotating_inertia_about_cg_neutral_kg_m2",
            ):
                self.assertIsNone(rotor[key])
            self.assertNotIn(
                "propeller_envelope_centre_cad_m", geo["main_propulsors"][name]
            )

    def test_propulsion_frame_follows_continuous_station(self):
        original = extract(self.doc)["exact_geometry"]["propulsion_reference_frame"]
        self.doc.MainPropulsionModule.RailPositionX = -12.4
        self.doc.recompute()
        geo = extract(self.doc)["exact_geometry"]
        frame = geo["propulsion_reference_frame"]
        self.assertEqual(frame["origin_cad_m"], [-0.0124, 0, 0])
        self.assertEqual(frame["pivot_positions_m"], original["pivot_positions_m"])
        for name in ("Port", "Starboard"):
            restored = [
                round(value + origin, 9)
                for value, origin in zip(
                    frame["pivot_positions_m"][name], frame["origin_cad_m"], strict=True
                )
            ]
            self.assertEqual(restored, geo["main_propulsors"][name]["pivot_cad_m"])

    def test_asymmetric_pivot_height_is_rejected(self):
        # Keep this side's fixed bearings coaxial while breaking pair alignment.
        self.doc.PortAssembly.Placement.Base.z += 1
        self.doc.recompute()
        with self.assertRaisesRegex(ValueError, "Pivot alignment changed"):
            extract(self.doc)

    def test_optical_pose_follows_shared_platform_and_retains_pitch(self):
        self.doc.ElectronicsEquipmentModule.RailPositionX = -61
        self.doc.InstrumentPitchStage.Pitch = 20
        self.doc.recompute()
        geo = extract(self.doc)["exact_geometry"]
        self.assertEqual(geo["optical_native_parent"], "InstrumentPitchStage")
        self.assertEqual(geo["instrument_pitch_pivot_cad_m"], [-0.061, 0, 0.0275])
        self.assertEqual(geo["instrument_pitch_deg"], 20)

    def test_optical_export_uses_actual_clamped_pose_without_mutating_controls(self):
        stage = self.doc.InstrumentPitchStage
        for command, expected in (
            (-20, -20),
            (-10, -10),
            (0, 0),
            (10, 10),
            (20, 20),
            (999, 20),
            (-999, -20),
        ):
            with self.subTest(command=command):
                stage.Pitch = command
                self.doc.recompute()
                stored = float(stage.Pitch)
                pose = stage.Placement.copy()
                expressions = list(stage.ExpressionEngine)
                geo = extract(self.doc)["exact_geometry"]
                self.assertEqual(geo["instrument_pitch_deg"], expected)
                self.assertEqual(float(stage.Pitch), stored)
                self.assertTrue(stage.Placement.isSame(pose, 1e-10))
                self.assertEqual(list(stage.ExpressionEngine), expressions)

    def test_optical_export_does_not_substitute_command_for_actual_local_pose(self):
        stage = self.doc.InstrumentPitchStage
        stage.Pitch = 0
        stage.setExpression("Placement.Rotation.Angle", None)
        stage.setExpression("Placement.Base.x", None)
        stage.setExpression("Placement.Base.z", None)
        stage.Placement = App.Placement(
            App.Vector(
                -8 * math.sin(math.radians(-7)),
                0,
                27.5 - 8 * math.cos(math.radians(-7)),
            ),
            App.Rotation(App.Vector(0, 1, 0), -7),
        )
        self.doc.recompute()
        self.assertEqual(float(stage.Pitch), 0)
        self.assertEqual(
            extract(self.doc)["exact_geometry"]["instrument_pitch_deg"], -7
        )

    def test_unexpected_optical_axis_and_actual_out_of_range_pose_are_rejected(self):
        stage = self.doc.InstrumentPitchStage
        stage.setExpression("Placement.Rotation.Angle", None)
        for axis, angle, message in (
            ((1, 0, 0), 5, "pure local-Y"),
            ((0, 0, 1), 5, "pure local-Y"),
            ((1, 1, 0), 5, "pure local-Y"),
            ((0, 1, 0), 21, "outside its declared limits"),
            ((0, 1, 0), -21, "outside its declared limits"),
        ):
            with self.subTest(axis=axis, angle=angle):
                stage.Placement.Rotation = App.Rotation(App.Vector(*axis), angle)
                self.doc.recompute()
                with self.assertRaisesRegex(ValueError, message):
                    extract(self.doc)

    def test_corrupt_optical_metadata_is_rejected(self):
        for field, value in (
            ("Pitch", float("nan")),
            ("Pitch", float("inf")),
            ("MinimumAngle", float("nan")),
            ("MaximumAngle", float("inf")),
            ("MinimumAngle", 20),
            ("MaximumAngle", -20),
            ("MaximumAngle", 30),
        ):
            stage = SimpleNamespace(
                Pitch=0, MinimumAngle=-20, MaximumAngle=20, Placement=App.Placement()
            )
            setattr(stage, field, value)
            with (
                self.subTest(field=field, value=value),
                self.assertRaisesRegex(ValueError, "metadata|limits"),
            ):
                instrument_pitch_degrees(stage)
        with self.assertRaisesRegex(ValueError, "metadata"):
            instrument_pitch_degrees(SimpleNamespace())

    def test_optical_cannot_silently_leave_shared_stage(self):
        self.doc.ElectronicsEquipmentModule.addObject(self.doc.OpticalFlowModule)
        with self.assertRaisesRegex(ValueError, "hierarchy"):
            extract(self.doc)

    def test_common_optical_rejects_a_stale_rail_mode_claim(self):
        self.doc.OpticalFlowModule.OpticalAttachmentMode = "rail"
        with self.assertRaisesRegex(ValueError, "attachment|legacy"):
            extract(self.doc)

    def test_unknown_vehicle_values_are_not_filled_with_zero(self):
        result = extract(self.doc)["whole_airship"]
        for key in (
            "total_mass_including_gas_kg",
            "cv_to_cg_vehicle_m",
            "inertia_about_cg_vehicle_diagonal_kg_m2",
            "aft_yaw_motor_position_vehicle_m",
            "cad_to_vehicle_rotation_matrix",
        ):
            self.assertIsNone(result[key])
        self.assertFalse(result["ready_for_system_identification"])

    def test_motor_axis_and_moment_equivalence_across_motion(self):
        # Independent physical check: force applied at a point displaced along
        # its own line of action has the same moment about any fixed origin.
        for angle in (-180, -90, -60, 0, 60, 90, 180):
            for name in ("Port", "Starboard"):
                pod = self.doc.getObject(name + "Pod")
                pod.Tilt = angle
                self.doc.recompute()
                axis = pod.getGlobalPlacement().Rotation.multVec(App.Vector(1, 0, 0))
                expected = App.Vector(
                    math.cos(math.radians(angle)), 0, -math.sin(math.radians(angle))
                )
                self.assertLess((axis - expected).Length, 1e-10)
                pivot = pod.getGlobalPlacement().Base
                disk = world_shape(
                    self.doc.getObject(name + "PropellerDisk")
                ).CenterOfMass
                self.assertLess(((disk - pivot) - 6.3 * axis).Length, 1e-7)
                for force_sign in (-1, 1):
                    force = force_sign * 2.5 * axis
                    self.assertLess(
                        (pivot.cross(force) - disk.cross(force)).Length, 1e-7
                    )

    def test_nonneutral_pose_is_rejected(self):
        self.doc.PortPod.Tilt = 20
        self.doc.recompute()
        with self.assertRaisesRegex(ValueError, "neutral"):
            extract(self.doc)

    def test_rotated_datum_is_rejected(self):
        self.doc.ContinuousRail.Placement.Rotation = App.Rotation(
            App.Vector(0, 0, 1), 90
        )
        with self.assertRaisesRegex(ValueError, "datum changed"):
            extract(self.doc)

    def test_rail_shape_must_remain_centred_in_its_local_frame(self):
        shape = self.doc.ContinuousRail.Shape.copy()
        shape.translate(App.Vector(1, 0, 0))
        self.doc.ContinuousRail.Shape = shape
        with self.assertRaisesRegex(ValueError, "datum changed"):
            extract(self.doc)

    def test_export_is_read_only_and_bound_to_exact_saved_file(self):
        with tempfile.TemporaryDirectory() as folder:
            cad = Path(folder) / "test.FCStd"
            # Synthetic validation identity solely to exercise IO, not a CAD
            # acceptance claim. The pinned fixture predates its config re-pin.
            self.doc.saveAs(str(cad))
            source = self.doc.DesignRegistry.SourceFingerprint
            App.closeDocument(self.doc_name)
            report = {
                "passed": True,
                "source_fingerprint": source,
                "source_hashes_after": {cad.name: file_sha256(cad)},
            }
            report_path = cad.with_name("test_validation.json")
            report_path.write_text(json.dumps(report))
            output = Path(folder) / "snapshot.json"
            original_hash = file_sha256(cad)
            with patch(
                "tools.cad_snapshot.source_fingerprint",
                return_value=source,
            ):
                export(cad, output)
                snapshot = json.loads(output.read_text())
                self.assertEqual(snapshot["schema_version"], 9)
                self.assertNotIn("simplified_geometry", snapshot)
                self.assertEqual(snapshot["basis"]["cad_sha256"], original_hash)
                self.assertEqual(file_sha256(cad), original_hash)
                report["source_hashes_after"][cad.name] = "wrong"
                report_path.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError, "exact saved"):
                    export(cad, output)
            with self.assertRaisesRegex(ValueError, "separate JSON"):
                export(cad, cad)
            with self.assertRaisesRegex(ValueError, "separate JSON"):
                export(cad, report_path)


if __name__ == "__main__":
    unittest.main()
