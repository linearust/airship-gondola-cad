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
            "gondola.print_export": types.SimpleNamespace(
                print_layout_check=Mock(return_value={"passed": True})
            ),
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
        self.preview.OUTPUT_DIR = self.output
        self.preview.source_fingerprint = Mock(return_value="current source")
        manifest_folder = self.output / "gondola_print_parts"
        manifest_folder.mkdir()
        (manifest_folder / "print_manifest.json").write_text("{}")

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
        power = types.SimpleNamespace(
            Name="power", Objects=[], PowerOptionModule=Mock(), AssemblyContext=Mock()
        )
        self.app.openDocument.side_effect = [assembly, layout, power]
        self.app.listDocuments.return_value = {
            "assembly": assembly,
            "layout": layout,
            "power": power,
        }
        self.preview.create_attachment_detail_document = Mock()
        self.gui.activeDocument.return_value.activeView.return_value.fitAll.side_effect = RuntimeError(
            "camera failure"
        )

        self.preview.render_previews(close_after=True)
        self.assertIs(power.PowerOptionModule.ViewObject.Visibility, True)
        self.assertIs(power.AssemblyContext.ViewObject.Visibility, False)
        self.assertFalse(self.read_state()["passed"])
        self.assertEqual(len(self.callbacks), 1)
        self.callbacks.pop(0)()  # Qt calls this after render_previews has returned.

        state = self.read_state()
        self.assertFalse(state["passed"])
        self.assertIn("camera failure", state["error"])
        self.assertEqual(state["status"], "failed")
        self.assertEqual(
            [call.args[0] for call in self.app.closeDocument.call_args_list],
            ["assembly", "layout", "power"],
        )
        self.gui.getMainWindow.return_value.close.assert_called_once()

    def test_direct_power_preview_shows_carrier_and_hides_clearances(self):
        def part(name, *, source=None, role="Reference"):
            return types.SimpleNamespace(
                Name=name,
                Label=name,
                SourceObjectName=source,
                SourceRole="Printed" if source == "BatteryMount" else role,
                Role=role,
                PropertiesList=["SourceObjectName"] if source is not None else [],
                ViewObject=types.SimpleNamespace(),
                isDerivedFrom=lambda kind: kind == "Part::Feature",
            )

        carrier = part("Context_BatteryMount", source="BatteryMount")
        unrelated = part("Context_ElectronicsMount", source="ElectronicsMount")
        board = part("PowerModule0")
        reserve = part("PowerModule0TopReserve", role="Clearance")
        doc = types.SimpleNamespace(
            PowerOptionModule=types.SimpleNamespace(
                PowerPackaging="DIRECT_CARRIER", ViewObject=types.SimpleNamespace()
            ),
            AssemblyContext=types.SimpleNamespace(ViewObject=types.SimpleNamespace()),
            Objects=[carrier, unrelated, board, reserve],
        )
        self.preview.style_power_option(doc)
        self.assertTrue(doc.AssemblyContext.ViewObject.Visibility)
        self.assertTrue(carrier.ViewObject.Visibility)
        self.assertTrue(board.ViewObject.Visibility)
        self.assertFalse(unrelated.ViewObject.Visibility)
        self.assertFalse(reserve.ViewObject.Visibility)

    def test_inconsistent_native_layout_prevents_rendering_and_invalidates_success(
        self,
    ):
        self.preview.print_layout_check.return_value = {"passed": False}
        assembly = types.SimpleNamespace(
            DesignRegistry=types.SimpleNamespace(SourceFingerprint="current source")
        )
        layout = types.SimpleNamespace(Name="layout")
        self.app.openDocument.side_effect = [assembly, layout]
        self.preview.render_previews()
        state = self.read_state()
        self.assertFalse(state["passed"])
        self.assertIn("Saved print layout is stale or inconsistent", state["error"])
        self.preview.print_layout_check.assert_called_once_with(
            layout, assembly.DesignRegistry, {}
        )
        self.assertEqual(self.callbacks, [])
        self.gui.activeDocument.assert_not_called()

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

    def test_optical_detail_includes_actual_supporting_carrier(self):
        host = types.SimpleNamespace(Name="BatteryEquipmentModule")
        optical = types.SimpleNamespace(
            OpticalAttachmentMode="carrier",
            CarrierHostName="BatteryEquipmentModule",
            getParentGeoFeatureGroup=lambda: host,
        )
        self.assertIs(self.preview.optical_detail_host(optical), host)
        optical.CarrierHostName = "ElectronicsEquipmentModule"
        with self.assertRaisesRegex(RuntimeError, "declared carrier parent"):
            self.preview.optical_detail_host(optical)
        optical.getParentGeoFeatureGroup = lambda: None
        with self.assertRaisesRegex(RuntimeError, "declared carrier parent"):
            self.preview.optical_detail_host(optical)

    def test_direct_rail_optical_detail_has_no_carrier_parent(self):
        optical = types.SimpleNamespace(
            OpticalAttachmentMode="rail", getParentGeoFeatureGroup=lambda: None
        )
        self.assertIs(self.preview.optical_detail_host(optical), optical)
        optical.getParentGeoFeatureGroup = lambda: types.SimpleNamespace(Name="Host")
        with self.assertRaisesRegex(RuntimeError, "top-level module"):
            self.preview.optical_detail_host(optical)


if __name__ == "__main__":
    unittest.main()
