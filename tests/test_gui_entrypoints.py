"""Persistent GUI sessions must execute the source they fingerprint."""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MACROS = ("build_gondola.FCMacro", "preview_gondola.FCMacro")


class GuiEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp_dir)
        self.records = []
        self.callbacks = []
        self.existing_document = {"user_edit": "retain this unsaved edit"}
        recorder = ModuleType("gui_test_recorder")
        recorder.records = self.records
        recorder.documents = [self.existing_document]
        gui = ModuleType("FreeCADGui")
        gui.activeDocument = lambda: SimpleNamespace(
            activeView=lambda: SimpleNamespace(
                viewAxonometric=lambda: None, fitAll=lambda: None
            )
        )
        pyside = ModuleType("PySide")
        pyside.QtCore = SimpleNamespace(
            QTimer=SimpleNamespace(
                singleShot=lambda delay, callback: self.callbacks.append(callback)
            )
        )
        self.enterContext(
            patch.dict(
                sys.modules,
                {
                    "FreeCADGui": gui,
                    "PySide": pyside,
                    "gui_test_recorder": recorder,
                },
            )
        )
        self.enterContext(patch.object(sys, "path", list(sys.path)))
        self.enterContext(patch.object(sys, "dont_write_bytecode", False))
        self.enterContext(patch.object(sys, "pycache_prefix", None))
        self.enterContext(patch.dict(os.environ, {"GONDOLA_CLOSE_AFTER_PREVIEW": "0"}))
        self.make_repo(self.root, "old")

    def make_repo(self, root, value):
        package = root / "gondola"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "settings.py").write_text(f"VALUE = {value!r}\n")
        (package / "provenance.py").write_text(
            "import hashlib\n"
            "from pathlib import Path\n"
            "def source_fingerprint():\n"
            "    return hashlib.sha256(\n"
            "        Path(__file__).with_name('settings.py').read_bytes()).hexdigest()\n"
        )
        imports = (
            "from .settings import VALUE\n"
            "from .provenance import source_fingerprint\n"
            "from gui_test_recorder import records, documents\n"
        )
        (package / "assembly.py").write_text(
            imports + "from types import SimpleNamespace\n"
            "def build_assembly():\n"
            "    records.append((VALUE, source_fingerprint()))\n"
            "    doc = SimpleNamespace(save=lambda: None)\n"
            "    documents.append(doc)\n"
            "    return doc\n"
            "def style_assembly(doc):\n"
            "    pass\n"
        )
        (package / "preview.py").write_text(
            imports + "def render_previews(close_after=False):\n"
            "    records.append((VALUE, source_fingerprint(), close_after))\n"
        )
        for macro in MACROS:
            shutil.copyfile(REPO_ROOT / macro, root / macro)

    def run_macro(self, macro, root=None, namespace=None):
        path = (root or self.root) / macro
        namespace = {} if namespace is None else namespace
        namespace["__file__"] = str(path)
        exec(compile(path.read_bytes(), str(path), "exec"), namespace)

    def render_pending(self):
        self.callbacks.pop(0)()

    def assert_latest_source(self, value, root=None):
        source = (root or self.root) / "gondola" / "settings.py"
        self.assertEqual(
            self.records[-1][:2],
            (value, hashlib.sha256(source.read_bytes()).hexdigest()),
        )
        self.assertIs(
            sys.modules["gui_test_recorder"].documents[0], self.existing_document
        )
        self.assertEqual(
            self.existing_document["user_edit"], "retain this unsaved edit"
        )

    def test_repeated_macros_reload_same_size_same_timestamp_source(self):
        for macro in MACROS:
            with self.subTest(macro=macro):
                source = self.root / "gondola" / "settings.py"
                source.write_text("VALUE = 'old'\n")
                self.run_macro(macro)
                if macro.startswith("preview"):
                    self.render_pending()
                self.assert_latest_source("old")
                self.assertTrue(list(source.parent.glob("__pycache__/settings.*.pyc")))
                previous = source.stat()
                source.write_text("VALUE = 'new'\n")
                os.utime(source, ns=(previous.st_atime_ns, previous.st_mtime_ns))
                self.run_macro(macro)
                if macro.startswith("preview"):
                    self.render_pending()
                self.assert_latest_source("new")

    def test_macro_selects_its_repository_after_another_copy_was_loaded(self):
        other_root = self.root / "other_checkout"
        self.make_repo(other_root, "alt")
        for macro in MACROS:
            with self.subTest(macro=macro):
                self.run_macro(macro)
                if macro.startswith("preview"):
                    self.render_pending()
                self.run_macro(macro, root=other_root)
                if macro.startswith("preview"):
                    self.render_pending()
                self.assert_latest_source("alt", root=other_root)
                self.run_macro(macro)
                if macro.startswith("preview"):
                    self.render_pending()
                self.assert_latest_source("old")
                self.assertEqual(sys.path.count(str(self.root)), 1)

    def test_preview_timer_keeps_its_callable_when_macro_namespace_is_reused(self):
        namespace = {}
        self.run_macro("preview_gondola.FCMacro", namespace=namespace)
        namespace["render_previews"] = lambda **kwargs: self.fail("replaced callback")
        os.environ["GONDOLA_CLOSE_AFTER_PREVIEW"] = "1"
        self.render_pending()
        self.assert_latest_source("old")
        self.assertFalse(self.records[-1][2])

    def test_cache_removal_failure_aborts_before_touching_documents(self):
        self.run_macro("build_gondola.FCMacro")
        self.records.clear()
        for macro in MACROS:
            with (
                self.subTest(macro=macro),
                patch.object(
                    Path, "unlink", side_effect=PermissionError("read-only cache")
                ),
            ):
                with self.assertRaisesRegex(PermissionError, "read-only cache"):
                    self.run_macro(macro)
                self.assertFalse(self.records)
                self.assertFalse(self.callbacks)
                self.assertEqual(
                    self.existing_document["user_edit"], "retain this unsaved edit"
                )


if __name__ == "__main__":
    unittest.main()
