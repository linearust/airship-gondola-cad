"""Optional crops must preserve the paired fit without modifying installed CAD."""

import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import FreeCAD as App
import Part

from gondola.config import BASELINE_FILE
from gondola.provenance import file_sha256
from tools.fit_coupon.export_joint import PARTS, export, extract, joint_checks


class JointFitCouponTests(unittest.TestCase):
    def setUp(self):
        self.digest = file_sha256(BASELINE_FILE)
        self.doc = App.openDocument(str(BASELINE_FILE))
        self.doc_name = self.doc.Name

    def tearDown(self):
        if self.doc_name in App.listDocuments():
            App.closeDocument(self.doc_name)
        self.assertEqual(file_sha256(BASELINE_FILE), self.digest)

    def shapes(self):
        return {name: shape for name, (_, shape) in extract(self.doc).items()}

    def test_three_crops_preserve_joint_and_source(self):
        shapes = self.shapes()
        self.assertEqual(set(shapes), set(PARTS))
        self.assertTrue(joint_checks(shapes)["passed"])
        self.assertEqual(len(shapes["RailPairCoupon"].Solids), 1)
        self.assertAlmostEqual(shapes["RailPairCoupon"].BoundBox.XLength, 62)
        contacts = {
            row["interface"]: row["area_mm2"]
            for row in joint_checks(shapes)["contacts"]
        }
        self.assertAlmostEqual(contacts["full_U_roof"], 696)
        for side in ("negative", "positive"):
            self.assertAlmostEqual(
                contacts[side + "_U_side"],
                58 * 10.3 - 18.4 * 3.2 - 2 * math.pi * 1.7**2,
            )
            self.assertAlmostEqual(contacts[side + "_rail_seat"], 62.5)

    def test_wrong_rail_station_loses_full_foot_support(self):
        shapes = self.shapes()
        shapes["RailPairCoupon"].translate(App.Vector(3, 0, 0))
        self.assertFalse(joint_checks(shapes)["passed"])

    def test_blocked_shared_bore_is_rejected(self):
        shapes = self.shapes()
        obstruction = Part.makeCylinder(
            1.7, 5, App.Vector(17, -11, 7), App.Vector(0, 1, 0)
        )
        shapes["SaddleJointCoupon"] = shapes["SaddleJointCoupon"].fuse(obstruction)
        self.assertFalse(joint_checks(shapes)["passed"])

    def test_missing_nut_bearing_floor_is_rejected_on_both_sides(self):
        for sign in (-1, 1):
            with self.subTest(sign=sign):
                shapes = self.shapes()
                floor = Part.makeCylinder(
                    2.7,
                    2,
                    App.Vector(sign * 17, sign * 6, 7),
                    App.Vector(0, sign, 0),
                )
                shapes["SaddleJointCoupon"] = shapes["SaddleJointCoupon"].cut(floor)
                self.assertFalse(joint_checks(shapes)["passed"])

    def test_interfering_fitted_U_is_rejected_without_bolt_forcing(self):
        shapes = self.shapes()
        shapes["SaddleJointCoupon"].translate(App.Vector(0, 0.1, 0))
        report = joint_checks(shapes)
        self.assertFalse(report["passed"])
        self.assertGreater(report["pair_overlap_mm3"][1], 1)

    def test_removed_continuous_side_wall_is_rejected(self):
        shapes = self.shapes()
        missing = Part.makeBox(4, 5, 4, App.Vector(23, 6, 3))
        shapes["SaddleJointCoupon"] = shapes["SaddleJointCoupon"].cut(missing)
        self.assertFalse(joint_checks(shapes)["passed"])

    def test_export_is_separate_read_only_and_round_tripped(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            cad = folder / "source.FCStd"
            self.doc.saveAs(str(cad))
            fingerprint = self.doc.DesignRegistry.SourceFingerprint
            App.closeDocument(self.doc_name)
            digest = file_sha256(cad)
            # Test-only validation identity exercises export IO, not certification.
            report = {
                "passed": True,
                "source_fingerprint": fingerprint,
                "source_hashes_after": {cad.name: digest},
            }
            report_path = folder / "source_validation.json"
            report_path.write_text(json.dumps(report))
            report_hash = file_sha256(report_path)
            output = folder / "optional"
            with patch(
                "tools.cad_snapshot.source_fingerprint", return_value=fingerprint
            ):
                export(cad, output)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["passed"])
            self.assertEqual(len(manifest["parts"]), 3)
            self.assertEqual(len(manifest["artifacts"]), 7)
            self.assertEqual(manifest["basis"]["cad_sha256"], digest)
            self.assertIn("M3x20", manifest["hardware"])
            self.assertIn("never use the bolts to force", manifest["limits"])
            for row in manifest["parts"]:
                self.assertEqual(row["installed_quantity"], 0)
                self.assertTrue(row["saved_crop_comparison"]["passed"])
            for name, digest in manifest["artifacts"].items():
                self.assertEqual(file_sha256(output / name), digest)
            self.assertEqual(file_sha256(cad), manifest["basis"]["cad_sha256"])
            self.assertEqual(file_sha256(report_path), report_hash)
            with self.assertRaisesRegex(ValueError, "new, separate"):
                export(cad, output)
            with self.assertRaisesRegex(ValueError, "new, separate"):
                export(cad, folder)


if __name__ == "__main__":
    unittest.main()
