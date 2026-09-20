"""Bundle identity gates run offline; geometry is checked in the CAD runtime."""

import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from gondola import bundle


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value))


class BundleIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gondola-bundle-test-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.stem = bundle.STEM
        self.folder = self.output / (self.stem + "_print_parts")
        self.folder.mkdir()
        self.fingerprint = sha256_bytes(b"source inputs")
        self.cad_path = self.output / (self.stem + ".FCStd")
        self.cad_path.write_bytes(b"saved CAD")
        self.cad_sha = bundle.file_sha256(self.cad_path)
        self.parts = []
        for index, quantity in enumerate((1, 1, 1, 1, 2, 4, 1, 1)):
            stl = f"part_{index}.stl"
            step = f"part_{index}.step"
            stl_data = f"STL {index}".encode()
            step_data = f"STEP {index}".encode()
            (self.folder / stl).write_bytes(stl_data)
            (self.folder / step).write_bytes(step_data)
            coupon = int(index >= 6)
            self.parts.append(
                {
                    "sku": f"part_{index}",
                    "file": stl,
                    "step_file": step,
                    "file_sha256": sha256_bytes(stl_data),
                    "step_sha256": sha256_bytes(step_data),
                    "quantity": quantity,
                    "installed_quantity": quantity - coupon,
                    "coupon_quantity": coupon,
                    "instances": [f"print_{index}_{i}" for i in range(quantity)],
                }
            )
        self.manifest = {
            "schema_version": 1,
            "source_fingerprint": self.fingerprint,
            "unique_stl_count": 8,
            "installed_printed_part_count": 10,
            "additional_coupon_printed_part_count": 2,
            "parts": self.parts,
        }
        self.manifest_path = self.folder / "print_manifest.json"
        write_json(self.manifest_path, self.manifest)
        self.bom = {
            "schema_version": 1,
            "source_fingerprint": self.fingerprint,
            "purchased_hardware_quantity": 22,
            "unique_purchase_spec_count": 5,
            "items": [
                {
                    "purchase_code": f"hardware_{index}",
                    "quantity": quantity,
                    "instances": [f"hardware_{index}_{i}" for i in range(quantity)],
                }
                for index, quantity in enumerate((4, 4, 8, 3, 3))
            ],
        }
        self.bom_path = self.output / (self.stem + "_hardware_bom.json")
        write_json(self.bom_path, self.bom)
        self.audit = {
            "passed": True,
            "source_fingerprint": self.fingerprint,
            "source_hashes_before": {self.cad_path.name: self.cad_sha},
            "source_hashes_after": {self.cad_path.name: self.cad_sha},
            "artifact_hashes": {
                name: bundle.file_sha256(path)
                for name, path in bundle.print_artifact_paths(
                    self.output, self.stem, self.manifest
                ).items()
            },
        }
        self.audit["artifact_hashes_before"] = dict(self.audit["artifact_hashes"])
        self.audit_path = self.output / (self.stem + "_validation.json")
        write_json(self.audit_path, self.audit)
        write_json(
            self.output / (self.stem + "_equipment_validation.json"),
            {
                "passed": True,
                "source_fingerprint": self.fingerprint,
                "source_sha256": self.cad_sha,
                "source_sha256_after": self.cad_sha,
            },
        )
        self.baseline_file = self.output / "frozen_baseline.FCStd"
        self.baseline_file.write_bytes(b"frozen geometry")
        self.baseline_sha = bundle.file_sha256(self.baseline_file)
        self.baseline_path = self.output / (self.stem + "_baseline_validation.json")
        baseline_hashes = {
            os.path.relpath(self.cad_path, bundle.ROOT): self.cad_sha,
            os.path.relpath(self.baseline_file, bundle.ROOT): self.baseline_sha,
        }
        self.baseline = {
            "passed": True,
            "source_fingerprint": self.fingerprint,
            "source_sha256": self.cad_sha,
            "baseline_sha256": self.baseline_sha,
            "file_hashes_before": baseline_hashes,
            "file_hashes_after": baseline_hashes,
        }
        write_json(self.baseline_path, self.baseline)
        self.baseline_patch = patch.multiple(
            bundle,
            BASELINE_FILE=self.baseline_file,
            BASELINE_SHA256=self.baseline_sha,
        )
        self.baseline_patch.start()
        self.addCleanup(self.baseline_patch.stop)
        self.image = self.stem + "_preview.png"
        (self.output / self.image).write_bytes(b"rendered preview")
        write_json(
            self.output / "preview_state.json",
            {
                "passed": True,
                "source_fingerprint": self.fingerprint,
                "source_sha256": self.cad_sha,
                "images": [self.image],
                "image_sha256": {self.image: sha256_bytes(b"rendered preview")},
            },
        )
        self.output_patch = patch.object(bundle, "OUTPUT_DIR", self.output)
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)
        self.source_patch = patch.object(
            bundle, "source_fingerprint", return_value=self.fingerprint
        )
        self.source_mock = self.source_patch.start()
        self.addCleanup(self.source_patch.stop)

    def package(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return bundle.build_bundle()

    def test_current_bundle_contains_only_whitelisted_artifacts(self):
        (self.folder / "obsolete.stl").write_bytes(b"old geometry")
        (self.folder / "private_notion.md").write_text("private source")
        (self.folder / "obsolete_validation.json").write_text("{}")
        archive = self.package()
        with zipfile.ZipFile(archive) as zipped:
            names = set(zipped.namelist())
            self.assertEqual(sum(name.endswith(".stl") for name in names), 8)
            self.assertEqual(sum(name.endswith(".step") for name in names), 8)
            self.assertNotIn("obsolete.stl", names)
            self.assertIn("validation/baseline.json", names)
            self.assertEqual(
                zipped.read("validation/baseline.json"), self.baseline_path.read_bytes()
            )
            self.assertFalse(any(name.endswith(".md") for name in names))
            self.assertFalse(
                json.loads(zipped.read("release_status.json"))["production_released"]
            )
            hashes = json.loads(zipped.read("package_hashes.json"))
            self.assertEqual(set(hashes["files"]), names - {"package_hashes.json"})
            for name, expected in hashes["files"].items():
                self.assertEqual(sha256_bytes(zipped.read(name)), expected)

    def test_changed_cad_cannot_publish(self):
        self.cad_path.write_bytes(b"changed CAD")
        with self.assertRaisesRegex(RuntimeError, "stale checks"):
            self.package()

    def test_changed_source_cannot_publish(self):
        self.source_mock.return_value = sha256_bytes(b"changed source")
        with self.assertRaisesRegex(RuntimeError, "Stale source"):
            self.package()

    def test_changed_export_cannot_publish(self):
        for key in ("file", "step_file"):
            with self.subTest(key=key):
                path = self.folder / self.parts[0][key]
                original = path.read_bytes()
                path.write_bytes(b"unvalidated export")
                with self.assertRaisesRegex(RuntimeError, "Stale or altered"):
                    self.package()
                path.write_bytes(original)

    def test_changed_manifest_or_bom_cannot_publish(self):
        for path in (self.manifest_path, self.bom_path):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.assertRaisesRegex(RuntimeError, "Stale or altered"):
                    self.package()
                path.write_bytes(original)

    def test_exports_must_match_both_validation_snapshots(self):
        self.audit["artifact_hashes_before"] = {}
        write_json(self.audit_path, self.audit)
        with self.assertRaisesRegex(RuntimeError, "Stale or altered"):
            self.package()

    def test_manifest_checksum_is_required_even_when_report_hashes_match(self):
        self.parts[0]["file_sha256"] = sha256_bytes(b"wrong")
        write_json(self.manifest_path, self.manifest)
        for field in ("artifact_hashes_before", "artifact_hashes"):
            self.audit[field][self.stem + "_print_parts/print_manifest.json"] = (
                bundle.file_sha256(self.manifest_path)
            )
        write_json(self.audit_path, self.audit)
        with self.assertRaisesRegex(RuntimeError, "checksum disagrees"):
            self.package()

    def test_malformed_manifests_are_rejected(self):
        for value in (
            [],
            {**self.manifest, "schema_version": 99},
            {**self.manifest, "parts": []},
        ):
            with self.subTest(value=value):
                write_json(self.manifest_path, value)
                with self.assertRaises(RuntimeError):
                    self.package()

    def test_manifest_cannot_escape_output_directory(self):
        self.parts[0]["file"] = "../../outside.stl"
        write_json(self.manifest_path, self.manifest)
        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            self.package()

    def test_manifest_cannot_reuse_an_instance(self):
        self.parts[1]["instances"][0] = self.parts[0]["instances"][0]
        write_json(self.manifest_path, self.manifest)
        with self.assertRaisesRegex(RuntimeError, "instances disagree"):
            self.package()

    def test_changed_preview_cannot_publish(self):
        (self.output / self.image).write_bytes(b"changed image")
        with self.assertRaisesRegex(RuntimeError, "Preview image changed"):
            self.package()

    def test_missing_baseline_comparison_cannot_publish(self):
        self.baseline_path.unlink()
        with self.assertRaisesRegex(RuntimeError, "Missing or malformed artifact"):
            self.package()

    def test_failed_or_stale_baseline_comparison_cannot_publish(self):
        mutations = {
            "passed": False,
            "source_sha256": sha256_bytes(b"older CAD"),
            "source_fingerprint": sha256_bytes(b"older source"),
            "baseline_sha256": sha256_bytes(b"different baseline"),
            "file_hashes_before": {},
            "file_hashes_after": {},
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                write_json(self.baseline_path, {**self.baseline, field: value})
                with self.assertRaisesRegex(RuntimeError, "baseline comparison"):
                    self.package()

    def test_replaced_frozen_baseline_cannot_publish(self):
        self.baseline_file.write_bytes(b"replacement geometry")
        with self.assertRaisesRegex(RuntimeError, "baseline comparison"):
            self.package()

    def test_inputs_changed_during_packaging_preserve_previous_archive(self):
        archive = self.package()
        previous_archive = archive.read_bytes()
        original_write = zipfile.ZipFile.writestr
        paths = (
            self.audit_path,
            self.output / (self.stem + "_equipment_validation.json"),
            self.baseline_path,
            self.output / "preview_state.json",
            self.output / self.image,
            self.manifest_path,
            self.bom_path,
            self.folder / self.parts[0]["file"],
            self.baseline_file,
        )
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                changed = False

                def mutate_after_snapshot(zipped, *args, **kwargs):
                    nonlocal changed
                    result = original_write(zipped, *args, **kwargs)
                    if not changed:
                        path.write_bytes(original + b"\nchanged during packaging")
                        changed = True
                    return result

                try:
                    with patch.object(
                        zipfile.ZipFile, "writestr", mutate_after_snapshot
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, "changed while packaging"
                        ):
                            self.package()
                    self.assertEqual(archive.read_bytes(), previous_archive)
                    self.assertFalse(list(self.output.glob(".gondola-bundle-*")))
                finally:
                    path.write_bytes(original)

    def test_failed_zip_write_preserves_previous_archive(self):
        archive = self.package()
        original = archive.read_bytes()
        with patch.object(
            zipfile.ZipFile, "writestr", side_effect=OSError("disk full")
        ):
            with self.assertRaisesRegex(RuntimeError, "disk full"):
                self.package()
        self.assertEqual(archive.read_bytes(), original)
        self.assertFalse(list(self.output.glob(".gondola-bundle-*")))

    def test_source_change_during_packaging_cannot_publish(self):
        self.source_mock.side_effect = [
            self.fingerprint,
            sha256_bytes(b"changed while packing"),
        ]
        with self.assertRaisesRegex(RuntimeError, "changed while packaging"):
            self.package()
        self.assertFalse(list(self.output.glob("*.zip")))


if __name__ == "__main__":
    unittest.main()
