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

    def test_two_crops_preserve_joint_and_source(self):
        shapes = self.shapes()
        self.assertEqual(set(shapes), set(PARTS))
        self.assertTrue(joint_checks(shapes)["passed"])
        self.assertEqual(len(shapes["RailPairCoupon"].Solids), 1)
        self.assertAlmostEqual(shapes["RailPairCoupon"].BoundBox.XLength, 50)
        self.assertAlmostEqual(shapes["FrameJointCoupon"].BoundBox.ZMax, 15)
        self.assertLess(joint_checks(shapes)["missing_roof_core_mm3"], 1e-6)

    def test_rail_station_beyond_supported_trim_is_rejected(self):
        shapes = self.shapes()
        shapes["RailPairCoupon"].translate(App.Vector(3.01, 0, 0))
        self.assertFalse(joint_checks(shapes)["passed"])

    def test_blocked_shared_bore_is_rejected(self):
        shapes = self.shapes()
        obstruction = Part.makeCylinder(
            1.7, 5, App.Vector(14, -5.25, 6), App.Vector(0, 1, 0)
        )
        shapes["FrameJointCoupon"] = shapes["FrameJointCoupon"].fuse(obstruction)
        self.assertFalse(joint_checks(shapes)["passed"])

    def test_missing_nut_bearing_floor_is_rejected_on_both_sides(self):
        for sign in (-1, 1):
            with self.subTest(sign=sign):
                shapes = self.shapes()
                floor = Part.makeCylinder(
                    2.7,
                    2,
                    App.Vector(sign * 14, sign * 1.25, 6),
                    App.Vector(0, sign, 0),
                )
                shapes["FrameJointCoupon"] = shapes["FrameJointCoupon"].cut(floor)
                self.assertFalse(joint_checks(shapes)["passed"])

    def test_interfering_fitted_U_is_rejected_without_bolt_forcing(self):
        shapes = self.shapes()
        shapes["FrameJointCoupon"].translate(App.Vector(0, 0.1, 0))
        report = joint_checks(shapes)
        self.assertFalse(report["passed"])
        self.assertGreater(report["pair_overlap_mm3"][0], 1)

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
            self.assertEqual(len(manifest["parts"]), 2)
            self.assertEqual(len(manifest["artifacts"]), 5)
            self.assertEqual(manifest["basis"]["cad_sha256"], digest)
            self.assertIn("M3x10", manifest["hardware"])
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


class JointFitCouponContactTests(unittest.TestCase):
    """Current source geometry checks independent of deliberate fixture promotion."""

    def setUp(self):
        from gondola.parts import propulsion, rail

        self.doc = App.newDocument("CurrentJointContactCoupon")
        module = self.doc.addObject("App::Part", "MainPropulsionModule")
        module.Placement.Base = App.Vector(14, 0, 0)
        for name, shape in (
            ("ContinuousRail", rail.rail_shape()),
            ("PropulsionFixedFrame", propulsion.fixed_frame_shape()),
        ):
            obj = self.doc.addObject("Part::Feature", name)
            if name != "ContinuousRail":
                module.addObject(obj)
            obj.Shape = shape
            obj.addProperty("App::PropertyRotation", "PrintRotation")
        self.doc.recompute()
        self.addCleanup(lambda: App.closeDocument(self.doc.Name))
        self.shapes = {name: shape for name, (_, shape) in extract(self.doc).items()}

    def test_current_crops_retain_paired_standard_top_seats(self):
        report = joint_checks(self.shapes)
        self.assertTrue(report["passed"], report)
        support = report["bottom_and_wall_support"]
        self.assertFalse(support["independent_wall_tilt_claimed"])
        self.assertEqual(support["top_bearing_z_mm"], 9.5)
        self.assertEqual(support["nominal_base_clearance_mm"], 1)
        self.assertAlmostEqual(support["top_bearing_area_total_mm2"], 80)
        for bore in report["M3_bores"]:
            self.assertEqual(abs(bore["axis_x_mm"]), 14)
            self.assertEqual(bore["axis_z_mm"], 6)

    def test_missing_top_seat_or_blocked_fit_is_rejected(self):
        frame = self.shapes["FrameJointCoupon"]
        for axis in (-14, 14):
            with self.subTest(axis=axis):
                cut = Part.makeBox(0.5, 2.5, 0.2, App.Vector(axis - 0.25, -1.25, 9.5))
                changed = frame.cut(cut)
                self.assertGreater(frame.Volume - changed.Volume, 0.2)
                report = joint_checks({**self.shapes, "FrameJointCoupon": changed})
                self.assertFalse(report["passed"])
                self.assertTrue(
                    any(
                        row["local_seat_geometry"]["top_bearing"][
                            "missing_roof_stock_mm3"
                        ]
                        > 0.01
                        for row in report["bottom_and_wall_support"]["wall_supports"]
                    )
                )
        blocked = frame.fuse(Part.makeBox(2, 2.5, 0.2, App.Vector(13, -1.25, 9.4)))
        report = joint_checks({**self.shapes, "FrameJointCoupon": blocked})
        self.assertFalse(report["passed"])
        self.assertGreater(report["pair_overlap_mm3"][0], 0.49)

    def test_supported_trim_keeps_both_standard_seats(self):
        for shift in (-3, 3):
            rail = self.shapes["RailPairCoupon"].copy()
            rail.translate(App.Vector(shift, 0, 0))
            report = joint_checks({**self.shapes, "RailPairCoupon": rail})
            self.assertTrue(report["passed"], report)
            self.assertAlmostEqual(
                report["bottom_and_wall_support"]["top_bearing_area_total_mm2"], 70
            )

    def test_cropped_frame_must_keep_its_roof_core(self):
        frame = self.shapes["FrameJointCoupon"]
        shortened = frame.common(Part.makeBox(50, 28, 14, App.Vector(-25, -14, 0)))
        result = joint_checks({**self.shapes, "FrameJointCoupon": shortened})
        self.assertFalse(result["passed"])
        self.assertGreater(result["missing_roof_core_mm3"], 1)


if __name__ == "__main__":
    unittest.main()
