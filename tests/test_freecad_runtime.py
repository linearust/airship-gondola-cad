"""Launcher failures must not reuse success from an earlier FreeCAD process."""

import contextlib
import hashlib
import io
import json
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gondola import cli, freecad_runtime


class FreeCADLauncher(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="gondola-runtime-")
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.cad = self.output / (freecad_runtime.ARTIFACT_STEM + ".FCStd")
        self.cad.write_bytes(b"native assembly")
        self.fingerprint = "current source fingerprint"
        for target, value in (
            ("locate_appimage", Mock(return_value=self.output / "FreeCAD.AppImage")),
            ("mounted_appimage", lambda _: contextlib.nullcontext(self.output)),
            ("source_fingerprint", Mock(return_value=self.fingerprint)),
        ):
            patcher = patch.object(freecad_runtime, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_result(self, env, **changes):
        state = {
            "passed": True,
            "run_id": env["GONDOLA_PREVIEW_RUN_ID"],
            "source_fingerprint": self.fingerprint,
            "source_sha256": hashlib.sha256(self.cad.read_bytes()).hexdigest(),
            **changes,
        }
        (self.output / "preview_state.json").write_text(json.dumps(state))

    def test_relative_source_is_resolved_before_child_changes_directory(self):
        with patch.object(
            freecad_runtime.subprocess, "run", return_value=Mock(returncode=0)
        ) as run:
            self.assertEqual(
                freecad_runtime.run_with_freecad(
                    "validate", self.output, source="saved.FCStd"
                ),
                0,
            )
        args = run.call_args.args[0]
        self.assertEqual(args[-2:], ["--source", str(Path("saved.FCStd").resolve())])
        self.assertEqual(run.call_args.kwargs["cwd"], freecad_runtime.REPO_ROOT)

    def test_preview_cannot_reuse_previous_success_when_child_writes_nothing(self):
        (self.output / "preview_state.json").write_text(
            json.dumps({"passed": True, "run_id": "previous invocation"})
        )
        with patch.object(freecad_runtime, "_run_preview_process", return_value=0):
            with self.assertRaisesRegex(RuntimeError, "did not finish"):
                freecad_runtime.run_with_freecad("preview", self.output)
        self.assertFalse(
            json.loads((self.output / "preview_state.json").read_text())["passed"]
        )

    def test_preview_rejects_result_from_another_invocation(self):
        def child(args, env):
            self.write_result(env, run_id="different invocation")
            return 0

        with patch.object(freecad_runtime, "_run_preview_process", side_effect=child):
            with self.assertRaisesRegex(RuntimeError, "this invocation"):
                freecad_runtime.run_with_freecad("preview", self.output)

    def test_current_preview_result_succeeds(self):
        def child(args, env):
            self.write_result(env)
            return 0

        with patch.object(freecad_runtime, "_run_preview_process", side_effect=child):
            self.assertEqual(
                freecad_runtime.run_with_freecad("preview", self.output), 0
            )

    def test_preview_rejects_stale_source_or_saved_cad(self):
        for changes, message in (
            ({"source_fingerprint": "old source"}, "Source changed"),
            ({"source_sha256": "old CAD"}, "Saved CAD changed"),
        ):
            with self.subTest(changes=changes):

                def child(args, env):
                    self.write_result(env, **changes)
                    return 0

                with patch.object(
                    freecad_runtime, "_run_preview_process", side_effect=child
                ):
                    with self.assertRaisesRegex(RuntimeError, message):
                        freecad_runtime.run_with_freecad("preview", self.output)

    def test_preview_failure_after_writing_success_invalidates_result(self):
        def child(args, env):
            self.write_result(env)
            raise RuntimeError("GUI did not close")

        with patch.object(freecad_runtime, "_run_preview_process", side_effect=child):
            with self.assertRaisesRegex(RuntimeError, "GUI did not close"):
                freecad_runtime.run_with_freecad("preview", self.output)
        self.assertFalse(
            json.loads((self.output / "preview_state.json").read_text())["passed"]
        )

    def test_preview_timeout_terminates_then_kills_unresponsive_process_group(self):
        process = Mock(pid=4321)
        process.wait.side_effect = [
            subprocess.TimeoutExpired(
                "FreeCAD", freecad_runtime.PREVIEW_TIMEOUT_SECONDS
            ),
            subprocess.TimeoutExpired(
                "FreeCAD", freecad_runtime.PROCESS_STOP_TIMEOUT_SECONDS
            ),
            -9,
        ]
        with (
            patch.object(
                freecad_runtime.subprocess, "Popen", return_value=process
            ) as popen,
            patch.object(freecad_runtime.os, "killpg") as killpg,
        ):
            with self.assertRaisesRegex(RuntimeError, "did not finish within"):
                freecad_runtime._run_preview_process(["FreeCAD"], {})
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(
            [call.args for call in killpg.call_args_list],
            [(4321, signal.SIGTERM), (4321, signal.SIGKILL)],
        )

    def test_interrupted_preview_cleans_up_child(self):
        process = Mock(pid=4321)
        process.wait.side_effect = [KeyboardInterrupt, -15]
        with (
            patch.object(freecad_runtime.subprocess, "Popen", return_value=process),
            patch.object(freecad_runtime.os, "killpg") as killpg,
        ):
            with self.assertRaises(KeyboardInterrupt):
                freecad_runtime._run_preview_process(["FreeCAD"], {})
        killpg.assert_called_once_with(4321, signal.SIGTERM)


class CommandLineErrors(unittest.TestCase):
    def test_missing_appimage_has_actionable_error_without_traceback(self):
        with tempfile.TemporaryDirectory(
            prefix="gondola-missing-runtime-"
        ) as directory:
            missing = Path(directory) / "missing.AppImage"
            stderr = io.StringIO()
            with patch.object(cli.importlib.util, "find_spec", return_value=None):
                with contextlib.redirect_stderr(stderr):
                    result = cli.main(["--freecad-appimage", str(missing), "build"])
        self.assertEqual(result, 1)
        self.assertIn("FreeCAD AppImage not found", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_cli_passes_resolved_source_to_launcher(self):
        with (
            patch.object(cli.importlib.util, "find_spec", return_value=None),
            patch.object(freecad_runtime, "run_with_freecad", return_value=0) as run,
        ):
            self.assertEqual(cli.main(["validate", "--source", "saved.FCStd"]), 0)
        self.assertEqual(run.call_args.args[3], Path("saved.FCStd").resolve())


if __name__ == "__main__":
    unittest.main()
