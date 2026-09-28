"""Manufacturer asset integrity, rigid normalization and independent copies."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = Part = None


@unittest.skipIf(App is None, "Requires the FreeCAD Python runtime")
class OEMServoHornTests(unittest.TestCase):
    def test_preserved_asset_and_archive_match_provenance(self):
        from gondola.config import REPO_ROOT
        from gondola.parts import oem_servo_horn as horn
        from gondola.provenance import file_sha256

        record = json.loads(
            (
                REPO_ROOT
                / "references/manufacturer/kst_x06_servo_horns_2026-09-28.json"
            ).read_text()
        )
        self.assertEqual(file_sha256(horn.STEP_PATH), horn.STEP_SHA256)
        self.assertEqual(record["selected_asset"]["sha256"], horn.STEP_SHA256)
        self.assertEqual(record["selected_asset"]["nominal_length_unit"], "mm")
        self.assertEqual(record["selected_asset"]["original_filename"], "X06半臂1.STEP")
        self.assertEqual(len(record["archive_members"]), 4)
        self.assertEqual(
            file_sha256(REPO_ROOT / record["archive"]["path"]),
            record["archive"]["sha256"],
        )

    def test_exact_solid_dimensions_and_factory_holes_are_preserved(self):
        from gondola.parts.oem_servo_horn import normalized_shape

        shape = normalized_shape()
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids), 1)
        self.assertAlmostEqual(shape.Volume, 202.72814863430688, places=6)
        bounds = shape.optimalBoundingBox(False, False)
        for key, expected in (
            ("XMin", -3.5),
            ("XMax", 15.2),
            ("YMin", 0.0),
            ("YMax", 3.5),
            ("ZMin", -3.5),
            ("ZMax", 3.5),
        ):
            self.assertAlmostEqual(getattr(bounds, key), expected, delta=1e-6)
        # Whole-depth bores plus their complete adjacent material rings reject
        # either filled holes or premature enlargement by the source loader.
        for x, diameter in ((4.5, 0.8), (6.8, 1.0), (10.0, 1.0), (13.2, 1.0)):
            with self.subTest(x=x, diameter=diameter):
                hole = Part.makeCylinder(
                    diameter / 2,
                    2.0,
                    App.Vector(x, 1.5, 0),
                    App.Vector(0, 1, 0),
                )
                outside = Part.makeCylinder(
                    diameter / 2 + 0.1,
                    2.0,
                    App.Vector(x, 1.5, 0),
                    App.Vector(0, 1, 0),
                )
                self.assertLess(abs(hole.common(shape).Volume), 1e-6)
                self.assertLess(abs(outside.cut(hole).cut(shape).Volume), 1e-6)

    def test_inverse_transform_recovers_the_complete_manufacturer_solid(self):
        from gondola.parts import oem_servo_horn as horn

        raw = Part.read(str(horn.STEP_PATH))
        recovered = horn.normalized_shape()
        recovered.translate(App.Vector(0, -1.5, 0))
        recovered.rotate(App.Vector(), App.Vector(1, 0, 0), 90)
        self.assertLess(abs(raw.cut(recovered).Volume), 1e-6)
        self.assertLess(abs(recovered.cut(raw).Volume), 1e-6)
        self.assertEqual(len(raw.Faces), len(recovered.Faces))

    def test_mutation_of_returned_shape_does_not_change_cached_geometry(self):
        from gondola.parts import oem_servo_horn as horn

        horn._raw_shape.cache_clear()
        with patch.object(horn.Part, "read", wraps=Part.read) as reader:
            first = horn.normalized_shape()
            first.scale(2)
            first.translate(App.Vector(100, 200, 300))
            second = horn.normalized_shape()
            self.assertIsNot(first, second)
            self.assertEqual(reader.call_count, 1)
            self.assertAlmostEqual(second.Volume, 202.72814863430688, places=6)
            self.assertAlmostEqual(second.BoundBox.YMin, 0.0, delta=1e-6)
            self.assertAlmostEqual(second.BoundBox.XMax, 15.2, delta=1e-6)

    def test_modified_asset_is_rejected_even_after_cache_is_populated(self):
        from gondola.parts import oem_servo_horn as horn

        horn.normalized_shape()
        with tempfile.TemporaryDirectory(prefix="gondola-oem-horn-") as directory:
            changed = Path(directory) / "changed.step"
            changed.write_bytes(horn.STEP_PATH.read_bytes() + b"\n")
            with patch.object(horn, "STEP_PATH", changed):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    horn.normalized_shape()


if __name__ == "__main__":
    unittest.main()
