"""Read-only geometry export and force-datum checks; run in FreeCAD Python."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import FreeCAD as App

from gondola.cad import world_shape
from gondola.config import BASELINE_FILE
from gondola.provenance import file_sha256
from tools.simulation.export_parameters import export, extract, vector_m


class UnitTests(unittest.TestCase):
    def test_si_conversion(self):
        self.assertEqual(vector_m((0, -74.9, 50)), [0, -0.0749, 0.05])


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
            geo["main_propulsors"]["Port"]["pivot_cad_m"], [0, 0.0751, 0.050]
        )
        self.assertEqual(
            geo["main_propulsors"]["Starboard"]["pivot_cad_m"], [0, -0.0749, 0.050]
        )
        frame = geo["propulsion_reference_frame"]
        self.assertEqual(frame["origin_cad_m"], [0, 0.0001, 0])
        self.assertEqual(
            frame["pivot_positions_m"],
            {"Port": [0, 0.075, 0.05], "Starboard": [0, -0.075, 0.05]},
        )
        self.assertEqual(geo["optical_pitch_pivot_cad_m"], [0.117, -0.0001, 0.035])
        self.assertEqual(geo["optical_carrier_host"], "BatteryEquipmentModule")
        self.assertEqual(geo["optical_mount_side"], "PositiveX")
        self.assertNotIn("optical_rail_station_x_mm", geo)
        self.assertEqual(geo["servo_to_output_angle_ratio"], -3)
        for name in ("Port", "Starboard"):
            self.assertEqual(
                geo["main_propulsors"][name]["pivot_cad_m"],
                geo["main_propulsors"][name]["motor_envelope_centre_cad_m"],
            )

    def test_propulsion_frame_follows_station_and_clamp_seating(self):
        original = extract(self.doc)["exact_geometry"]["propulsion_reference_frame"]
        self.doc.MainPropulsionModule.RailPositionX = 18
        self.doc.AssemblySettings.PropulsionClampApproach = "NegativeY"
        self.doc.recompute()
        geo = extract(self.doc)["exact_geometry"]
        frame = geo["propulsion_reference_frame"]
        self.assertEqual(frame["origin_cad_m"], [0.018, -0.0001, 0])
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
        self.doc.PortPod.Placement.Base.z += 1
        self.doc.recompute()
        with self.assertRaisesRegex(ValueError, "Pivot alignment changed"):
            extract(self.doc)

    def test_optical_pose_follows_carrier_translation_and_selected_side(self):
        self.doc.BatteryEquipmentModule.RailPositionX = 108
        self.doc.OpticalFlowModule.MountSide = "NegativeX"
        self.doc.OpticalPitchStage.Pitch = 20
        self.doc.recompute()
        geo = extract(self.doc)["exact_geometry"]
        self.assertEqual(geo["optical_carrier_host"], "BatteryEquipmentModule")
        self.assertEqual(geo["optical_mount_side"], "NegativeX")
        self.assertEqual(geo["optical_pitch_pivot_cad_m"], [0.081, -0.0001, 0.035])
        self.assertEqual(geo["optical_pitch_deg"], 20)

    def test_optical_metadata_cannot_name_a_different_parent(self):
        self.doc.OpticalFlowModule.CarrierHostName = "ElectronicsEquipmentModule"
        with self.assertRaisesRegex(ValueError, "Optical carrier binding"):
            extract(self.doc)

    def test_legacy_independent_optical_rail_control_is_rejected(self):
        self.doc.OpticalFlowModule.addProperty("App::PropertyLength", "RailPositionX")
        with self.assertRaisesRegex(ValueError, "Optical carrier binding"):
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
                self.assertLess(((disk - pivot) - 12 * axis).Length, 1e-7)
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
                "tools.simulation.export_parameters.source_fingerprint",
                return_value=source,
            ):
                export(cad, output)
                snapshot = json.loads(output.read_text())
                self.assertEqual(snapshot["schema_version"], 4)
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
