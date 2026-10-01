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

    def make_tool_inputs(self):
        tools = {}
        for name in ("exporter", "snapshot_helper", "motion_plan"):
            path = self.root / (name + ".py")
            path.write_text("# original " + name + "\n")
            tools[name + "_sha256"] = path
        return tools

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

    def test_tool_hashes_are_captured_without_changing_existing_provenance_schema(self):
        tools = self.make_tool_inputs()
        expected = {name: file_sha256(path) for name, path in tools.items()}
        with cad_snapshot.open_validated_cad(
            self.cad, self.output, tool_inputs=tools
        ) as snapshot:
            tools.clear()
            self.assertEqual(snapshot.tool_hashes, expected)
            detached = snapshot.tool_hashes
            detached.clear()
            self.assertEqual(snapshot.tool_hashes, expected)
        snapshot.write_json(
            {"basis": {**snapshot.provenance(), **snapshot.tool_hashes}}
        )
        basis = json.loads(self.output.read_text())["basis"]
        self.assertEqual(set(basis), set(snapshot.provenance()) | set(expected))
        self.assertEqual({key: basis[key] for key in expected}, expected)

    def test_output_cannot_alias_any_tool_input(self):
        tools = self.make_tool_inputs()
        for path in tools.values():
            for kind in ("same", "symlink", "hardlink"):
                with self.subTest(tool=path.name, kind=kind):
                    alias = self.root / f"{path.stem}-{kind}.json"
                    if kind == "same":
                        alias = path
                    elif kind == "symlink":
                        alias.symlink_to(path)
                    else:
                        os.link(path, alias)
                    before = file_sha256(path)
                    with self.assertRaisesRegex(ValueError, "not an input"):
                        with cad_snapshot.open_validated_cad(
                            self.cad, alias, tool_inputs=tools
                        ):
                            self.fail("Aliased tool output was accepted")
                    self.assertEqual(file_sha256(path), before)
        self.app.openDocument.assert_not_called()

    def test_changed_tools_during_extraction_reject_the_result(self):
        tools = self.make_tool_inputs()
        for path in tools.values():
            with self.subTest(tool=path.name):
                self.app.closeDocument.reset_mock()
                with self.assertRaisesRegex(RuntimeError, "Export tool changed"):
                    with cad_snapshot.open_validated_cad(
                        self.cad, self.output, tool_inputs=tools
                    ):
                        path.write_text(path.read_text() + "# changed\n")
                self.app.closeDocument.assert_called_once_with(self.doc.Name)
                self.assert_previous_output()

    def test_tool_change_during_json_encoding_preserves_output_and_cleans_temp(self):
        tools = self.make_tool_inputs()
        with cad_snapshot.open_validated_cad(
            self.cad, self.output, tool_inputs=tools
        ) as snapshot:
            pass
        before = set(self.root.iterdir())
        dumps = json.dumps

        def encode_and_change_tool(*args, **kwargs):
            payload = dumps(*args, **kwargs)
            tools["motion_plan_sha256"].write_text("# changed during encoding\n")
            return payload

        with patch.object(
            cad_snapshot.json, "dumps", side_effect=encode_and_change_tool
        ):
            with self.assertRaisesRegex(RuntimeError, "Export tool changed"):
                snapshot.write_json({"new": True})
        self.assert_previous_output()
        self.assertEqual(set(self.root.iterdir()), before)

    def test_late_tool_alias_is_rejected_before_output_replacement(self):
        tools = self.make_tool_inputs()
        with cad_snapshot.open_validated_cad(
            self.cad, self.output, tool_inputs=tools
        ) as snapshot:
            pass
        path = tools["exporter_sha256"]
        before = file_sha256(path)
        self.output.unlink()
        os.link(path, self.output)
        with self.assertRaisesRegex(ValueError, "not an input"):
            snapshot.write_json({"new": True})
        self.assertEqual(file_sha256(path), before)

    def test_simulation_export_rejects_tool_change_during_extraction(self):
        from tools.simulation import export_parameters as exporter

        tool = self.make_tool_inputs()["exporter_sha256"]

        def extract_and_change_tool(_):
            tool.write_text("# changed while extracting simulation data\n")
            return {"synthetic_result": 1}

        with (
            patch.object(exporter, "__file__", str(tool)),
            patch.object(exporter, "extract", side_effect=extract_and_change_tool),
            self.assertRaisesRegex(RuntimeError, "Export tool changed"),
        ):
            exporter.export(self.cad, self.output)
        self.app.closeDocument.assert_called_once_with(self.doc.Name)
        self.assert_previous_output()

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
