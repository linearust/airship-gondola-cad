"""Derivative exports must preserve their validated inputs and prior output."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gondola.provenance import file_sha256
from tools import cad_snapshot


class ValidatedCADSnapshot(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="gondola-snapshot-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.cad = self.root / "assembly.FCStd"
        self.cad.write_bytes(b"synthetic native CAD for IO tests")
        self.report_path = self.root / "assembly_validation.json"
        self.fingerprint = "synthetic-current-source"
        self.report = {
            "passed": True,
            "source_fingerprint": self.fingerprint,
            "source_hashes_after": {self.cad.name: file_sha256(self.cad)},
        }
        self.write_report()
        self.output = self.root / "snapshot.json"
        self.previous_output = b'{"previous": true}\n'
        self.output.write_bytes(self.previous_output)
        self.doc = SimpleNamespace(
            Name="SnapshotTest",
            DesignRegistry=SimpleNamespace(SourceFingerprint=self.fingerprint),
        )
        self.app = SimpleNamespace(
            openDocument=Mock(return_value=self.doc), closeDocument=Mock()
        )
        patches = (
            patch.dict(sys.modules, {"FreeCAD": self.app}),
            patch.object(
                cad_snapshot, "source_fingerprint", return_value=self.fingerprint
            ),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_report(self):
        self.report_path.write_text(json.dumps(self.report) + "\n")

    def assert_previous_output(self):
        self.assertEqual(self.output.read_bytes(), self.previous_output)

    def test_success_preserves_inputs_and_records_the_exact_evidence(self):
        input_hashes = {
            path: file_sha256(path) for path in (self.cad, self.report_path)
        }
        with cad_snapshot.open_validated_cad(self.cad, self.output) as snapshot:
            self.assertIs(snapshot.doc, self.doc)
            self.assertEqual(snapshot.cad_path, self.cad)
            self.assertEqual(snapshot.output_path, self.output)
            self.assertEqual(snapshot.report_path, self.report_path)
            self.assertEqual(snapshot.report, self.report)
        self.app.closeDocument.assert_called_once_with(self.doc.Name)
        provenance = snapshot.provenance()
        self.assertEqual(
            provenance,
            {
                "cad_file": self.cad.name,
                "cad_sha256": input_hashes[self.cad],
                "source_fingerprint": self.fingerprint,
                "validation_sha256": input_hashes[self.report_path],
            },
        )
        snapshot.write_json({"basis": provenance, "value": 1}, indent=2)
        self.assertEqual(json.loads(self.output.read_text())["basis"], provenance)
        for path, digest in input_hashes.items():
            self.assertEqual(file_sha256(path), digest)

    def test_output_cannot_alias_cad_or_validation_by_name_symlink_or_hardlink(self):
        for input_path in (self.cad, self.report_path):
            for alias_kind in ("same", "symlink", "hardlink"):
                with self.subTest(input=input_path.name, alias=alias_kind):
                    alias = self.root / f"alias-{input_path.stem}-{alias_kind}.json"
                    if alias_kind == "same":
                        alias = input_path
                    elif alias_kind == "symlink":
                        alias.symlink_to(input_path)
                    else:
                        os.link(input_path, alias)
                    digest = file_sha256(input_path)
                    with self.assertRaises(ValueError):
                        with cad_snapshot.open_validated_cad(self.cad, alias):
                            self.fail("Aliased output was accepted")
                    self.assertEqual(file_sha256(input_path), digest)
        self.app.openDocument.assert_not_called()

    def test_non_json_output_is_rejected_before_opening_cad(self):
        with self.assertRaises(ValueError):
            with cad_snapshot.open_validated_cad(self.cad, self.root / "out.txt"):
                self.fail("Non-JSON output was accepted")
        self.app.openDocument.assert_not_called()

    def test_validation_requires_literal_success_current_source_and_exact_cad(self):
        original = dict(self.report)
        cases = (
            {"passed": False},
            {"passed": "false"},
            {"passed": 1},
            {"source_fingerprint": "old source"},
            {"source_hashes_after": {self.cad.name: "wrong bytes"}},
            {"source_hashes_after": {}},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                self.report = {**original, **changes}
                self.write_report()
                with self.assertRaises(ValueError):
                    with cad_snapshot.open_validated_cad(self.cad, self.output):
                        self.fail("Unvalidated source was accepted")
                self.assert_previous_output()
        self.app.openDocument.assert_not_called()

    def test_stale_native_registry_is_rejected_and_document_is_closed(self):
        self.doc.DesignRegistry.SourceFingerprint = "old native source"
        with self.assertRaises(ValueError):
            with cad_snapshot.open_validated_cad(self.cad, self.output):
                self.fail("Stale native source was accepted")
        self.app.closeDocument.assert_called_once_with(self.doc.Name)
        self.assert_previous_output()

    def test_extraction_exception_closes_document_without_replacing_output(self):
        error = RuntimeError("extraction failed")
        with self.assertRaises(RuntimeError) as raised:
            with cad_snapshot.open_validated_cad(self.cad, self.output):
                raise error
        self.assertIs(raised.exception, error)
        self.app.closeDocument.assert_called_once_with(self.doc.Name)
        self.assert_previous_output()

    def test_changed_inputs_during_extraction_close_document_and_reject_result(self):
        original_cad = self.cad.read_bytes()
        original_report = self.report_path.read_bytes()
        for changed in ("cad", "report", "source"):
            with self.subTest(changed=changed):
                self.cad.write_bytes(original_cad)
                self.report_path.write_bytes(original_report)
                cad_snapshot.source_fingerprint.return_value = self.fingerprint
                self.app.closeDocument.reset_mock()
                with self.assertRaises(RuntimeError):
                    with cad_snapshot.open_validated_cad(self.cad, self.output):
                        if changed == "cad":
                            self.cad.write_bytes(b"changed native CAD")
                        elif changed == "report":
                            self.report_path.write_text('{"passed": false}\n')
                        else:
                            cad_snapshot.source_fingerprint.return_value = "new source"
                self.app.closeDocument.assert_called_once_with(self.doc.Name)
                self.assert_previous_output()

    def test_late_input_change_is_rejected_before_output_replacement(self):
        with cad_snapshot.open_validated_cad(self.cad, self.output) as snapshot:
            pass
        self.report_path.write_text('{"passed": false}\n')
        with self.assertRaises(RuntimeError):
            snapshot.write_json({"new": True})
        self.assert_previous_output()

    def test_nonfinite_json_preserves_previous_output_and_cleans_temporary_file(self):
        with cad_snapshot.open_validated_cad(self.cad, self.output) as snapshot:
            pass
        before = set(self.root.iterdir())
        with self.assertRaises(ValueError):
            snapshot.write_json({"value": float("nan")}, indent=2)
        self.assert_previous_output()
        self.assertEqual(set(self.root.iterdir()), before)

    def test_failed_atomic_replacement_preserves_output_and_cleans_temporary_file(self):
        with cad_snapshot.open_validated_cad(self.cad, self.output) as snapshot:
            pass
        before = set(self.root.iterdir())
        with patch.object(
            cad_snapshot.os, "replace", side_effect=OSError("replacement failed")
        ):
            with self.assertRaises(OSError):
                snapshot.write_json({"new": True})
        self.assert_previous_output()
        self.assertEqual(set(self.root.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
