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
        self.stem = bundle.ARTIFACT_STEM
        self.folder = self.output / (self.stem + "_print_parts")
        self.folder.mkdir()
        self.fingerprint = sha256_bytes(b"source inputs")
        self.cad_path = self.output / (self.stem + ".FCStd")
        self.cad_path.write_bytes(b"saved CAD")
        self.cad_sha = bundle.file_sha256(self.cad_path)
        self.parts = []
        inventory = bundle.EXPECTED_INVENTORY
        installed_skus = inventory["unique_print_files"] - inventory["fit_coupons"]
        quantities = [1] * inventory["unique_print_files"]
        quantities[0] += inventory["installed_prints"] - installed_skus
        for index, quantity in enumerate(quantities):
            stl = f"part_{index}.stl"
            step = f"part_{index}.step"
            stl_data = f"STL {index}".encode()
            step_data = f"STEP {index}".encode()
            (self.folder / stl).write_bytes(stl_data)
            (self.folder / step).write_bytes(step_data)
            coupon = int(index >= installed_skus)
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
            "schema_version": bundle.ARTIFACT_SCHEMA_VERSION,
            "source_fingerprint": self.fingerprint,
            "unique_stl_count": inventory["unique_print_files"],
            "installed_printed_part_count": inventory["installed_prints"],
            "additional_coupon_printed_part_count": inventory["fit_coupons"],
            "release_status": bundle.release_status(),
            "parts": self.parts,
        }
        self.manifest_path = self.folder / "print_manifest.json"
        write_json(self.manifest_path, self.manifest)
        self.bom = {
            "schema_version": bundle.ARTIFACT_SCHEMA_VERSION,
            "source_fingerprint": self.fingerprint,
            "purchased_hardware_quantity": inventory["purchased_hardware"],
            "unique_purchase_spec_count": inventory["purchased_hardware_types"],
            "purchase_scope": bundle.hardware_bom_scope(),
            "items": [
                {
                    "sku": sku,
                    "material": bundle.HARDWARE_MATERIALS[sku],
                    "purchase_code": bundle.purchase_code(
                        sku, bundle.HARDWARE_MATERIALS[sku]
                    ),
                    "quantity": quantity,
                    "instances": [f"hardware_{index}_{i}" for i in range(quantity)],
                }
                for index, (sku, quantity) in enumerate(
                    bundle.PURCHASED_HARDWARE_QUANTITIES.items()
                )
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
                "hardware_bom_sha256_before": bundle.file_sha256(self.bom_path),
                "hardware_bom_sha256_after": bundle.file_sha256(self.bom_path),
            },
        )
        self.baseline_file = self.output / "frozen_baseline.FCStd"
        self.baseline_file.write_bytes(b"frozen geometry")
        self.baseline_sha = bundle.file_sha256(self.baseline_file)
        self.baseline_path = self.output / (self.stem + "_baseline_validation.json")
        baseline_hashes = {
            os.path.relpath(self.cad_path, bundle.REPO_ROOT): self.cad_sha,
            os.path.relpath(self.baseline_file, bundle.REPO_ROOT): self.baseline_sha,
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
            self.assertEqual(
                sum(name.endswith(".stl") for name in names),
                bundle.EXPECTED_INVENTORY["unique_print_files"],
            )
            self.assertEqual(
                sum(name.endswith(".step") for name in names),
                bundle.EXPECTED_INVENTORY["unique_print_files"],
            )
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

    def test_bom_cannot_substitute_specs_while_preserving_total_quantity(self):
        for field, replacement in (
            ("sku", "M2_HEX_NUT"),
            ("material", "Nylon PA6"),
            ("purchase_code", "unverified substitution"),
        ):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(self.bom))
                changed["items"][0][field] = replacement
                with self.assertRaisesRegex(RuntimeError, "specifications disagree"):
                    bundle._validate_bom(changed)
        changed = json.loads(json.dumps(self.bom))
        changed["items"][0]["quantity"] += 1
        changed["items"][1]["quantity"] -= 1
        with self.assertRaisesRegex(RuntimeError, "specifications disagree"):
            bundle._validate_bom(changed)

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

    def test_equipment_report_must_validate_the_packaged_bom(self):
        report_path = self.output / (self.stem + "_equipment_validation.json")
        report = json.loads(report_path.read_text())
        for field in ("hardware_bom_sha256_before", "hardware_bom_sha256_after"):
            for value in (None, sha256_bytes(b"previous BOM")):
                with self.subTest(field=field, value=value):
                    write_json(report_path, {**report, field: value})
                    with self.assertRaisesRegex(
                        RuntimeError, "equipment BOM validation"
                    ):
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

    def test_release_and_purchase_scope_must_match_current_contract(self):
        for path, document, field, message in (
            (self.manifest_path, self.manifest, "release_status", "release status"),
            (self.bom_path, self.bom, "purchase_scope", "purchase scope"),
        ):
            for replacement in (None, {"production_released": True}):
                with self.subTest(field=field, replacement=replacement):
                    original = document[field]
                    document[field] = replacement
                    write_json(path, document)
                    name = str(path.relative_to(self.output))
                    for snapshot in ("artifact_hashes_before", "artifact_hashes"):
                        self.audit[snapshot][name] = bundle.file_sha256(path)
                    write_json(self.audit_path, self.audit)
                    try:
                        with self.assertRaisesRegex(RuntimeError, message):
                            self.package()
                    finally:
                        document[field] = original
                        write_json(path, document)
                        for snapshot in ("artifact_hashes_before", "artifact_hashes"):
                            self.audit[snapshot][name] = bundle.file_sha256(path)
                        write_json(self.audit_path, self.audit)

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
