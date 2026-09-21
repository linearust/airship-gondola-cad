"""Exercise delayed Qt failure handling without importing the CAD runtime."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class PreviewCallbacks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="gondola-preview-")
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.app = Mock()
        self.gui = Mock()
        self.callbacks = []
        qt = types.SimpleNamespace(
            QTimer=types.SimpleNamespace(
                singleShot=lambda delay, callback: self.callbacks.append(callback)
            )
        )
        modules = {
            "FreeCAD": self.app,
            "FreeCADGui": self.gui,
            "Part": Mock(),
            "PySide": types.SimpleNamespace(QtCore=qt),
            "gondola.assembly": types.SimpleNamespace(style_assembly=Mock()),
            "gondola.parts.stack_interface": Mock(),
            "gondola.cad": types.SimpleNamespace(
                create_group=Mock(),
                world_shape=Mock(),
                translated_shape=Mock(),
                belongs_to_group=Mock(),
            ),
        }
        source = Path(__file__).resolve().parents[1] / "gondola" / "preview.py"
        spec = importlib.util.spec_from_file_location("preview_under_test", source)
        self.preview = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(self.preview)
        # A previously imported native submodule may remain on its package.
        self.preview.stack_interface = modules["gondola.parts.stack_interface"]
        self.preview.OUT = self.output
        self.preview.source_fingerprint = Mock(return_value="current source")

    def read_state(self):
        return json.loads((self.output / "preview_state.json").read_text())

    def test_delayed_camera_failure_overwrites_old_success_and_closes_gui(self):
        (self.output / "preview_state.json").write_text('{"passed": true}')
        registry = types.SimpleNamespace(
            SourceFingerprint="current source",
            PrintedParts=[],
            HardwareParts=[],
            ReferenceParts=[],
            TapeReferences=[],
        )
        assembly = types.SimpleNamespace(
            Name="assembly",
            DesignRegistry=registry,
            OpticalFlowModule=Mock(),
            BatteryEquipmentModule=Mock(),
            ElectronicsEquipmentModule=Mock(),
        )
        layout = types.SimpleNamespace(Name="layout", Objects=[])
        self.app.openDocument.side_effect = [assembly, layout]
        self.app.listDocuments.return_value = {"assembly": assembly, "layout": layout}
        self.preview.create_attachment_detail_document = Mock()
        self.gui.activeDocument.return_value.activeView.return_value.fitAll.side_effect = RuntimeError(
            "camera failure"
        )

        self.preview.render_previews(close_after=True)
        self.assertFalse(self.read_state()["passed"])
        self.assertEqual(len(self.callbacks), 1)
        self.callbacks.pop(0)()  # Qt calls this after render_previews has returned.

        state = self.read_state()
        self.assertFalse(state["passed"])
        self.assertIn("camera failure", state["error"])
        self.assertEqual(state["status"], "failed")
        self.assertEqual(
            [call.args[0] for call in self.app.closeDocument.call_args_list],
            ["assembly", "layout"],
        )
        self.gui.getMainWindow.return_value.close.assert_called_once()

    def test_pending_callbacks_do_not_run_after_first_failure(self):
        session = self.preview._PreviewSession(self.output, close_after=False)
        failing = Mock(side_effect=OSError("cannot write preview"))
        later = Mock()
        session.schedule(1, failing)
        session.schedule(2, later)
        for callback in self.callbacks:
            callback()
        failing.assert_called_once()
        later.assert_not_called()
        self.assertFalse(self.read_state()["passed"])
        self.gui.getMainWindow.assert_not_called()


if __name__ == "__main__":
    unittest.main()
