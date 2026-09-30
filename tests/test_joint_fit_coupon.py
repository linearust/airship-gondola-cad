"""Optional crops must preserve the paired fit without modifying installed CAD."""

import json
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

    def test_wrong_rail_station_loses_full_foot_support(self):
        shapes = self.shapes()
        shapes["RailPairCoupon"].translate(App.Vector(3, 0, 0))
        self.assertFalse(joint_checks(shapes)["passed"])

    def test_blocked_shared_bore_is_rejected(self):
        shapes = self.shapes()
        obstruction = Part.makeCylinder(
            1.7, 4.5, App.Vector(17, -9.75, 7), App.Vector(0, 1, 0)
        )
        shapes["SaddleJointCoupon"] = shapes["SaddleJointCoupon"].fuse(obstruction)
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
