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
from tools.simulation.export_parameters import approximation, export, extract, vector_m


class ApproximationTests(unittest.TestCase):
    def test_si_conversion(self):
        self.assertEqual(vector_m((0, -65.4, 48.2)), [0, -0.0654, 0.0482])

    def test_error_is_position_distance_not_relative_torque_error(self):
        points = {"Port": [0, 0.0656, 0.0482], "Starboard": [0, -0.0654, 0.0482]}
        result = approximation(points)
        self.assertTrue(result["available"])
        self.assertAlmostEqual(
            result["position_error_m"]["Port"], math.hypot(0.0006, 0.0018)
        )
        self.assertEqual(
            result["position_error_m"], result["absolute_moment_error_bound_Nm_per_N"]
        )

    def test_moved_module_does_not_get_old_approximation(self):
        result = approximation(
            {"Port": [0.01, 0.0656, 0.0482], "Starboard": [0.01, -0.0654, 0.0482]}
        )
        self.assertFalse(result["available"])
        self.assertNotIn("pivot_positions_cad_m", result)

    def test_nonfinite_or_wrong_dimension_is_rejected(self):
        for bad in ([0, float("nan"), 0.05], [0, float("inf"), 0.05], [0, 0.05]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                approximation({"Port": bad, "Starboard": [0, -0.065, 0.05]})


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
        self.assertAlmostEqual(geo["main_pivot_span_m"], 0.131)
        self.assertEqual(
            geo["main_propulsors"]["Port"]["pivot_cad_m"], [0, 0.0656, 0.0482]
        )
        self.assertEqual(
            geo["main_propulsors"]["Starboard"]["pivot_cad_m"], [0, -0.0654, 0.0482]
        )
        self.assertEqual(geo["optical_pitch_pivot_cad_m"], [0.14, -0.0001, 0.0374])
        self.assertEqual(geo["servo_to_output_angle_ratio"], -3)
        for name in ("Port", "Starboard"):
            self.assertEqual(
                geo["main_propulsors"][name]["pivot_cad_m"],
                geo["main_propulsors"][name]["motor_envelope_centre_cad_m"],
            )

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
                self.assertEqual(
                    json.loads(output.read_text())["basis"]["cad_sha256"], original_hash
                )
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
