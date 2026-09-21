"""Run with an installed FreeCAD AppImage without storing a temporary mount path.

The mount belongs to this invocation and is released when its child exits.
A normal FreeCAD installation can run the same build_gondola/preview_gondola macros directly.
"""

import contextlib
import json
import os
import selectors
import signal
import subprocess
import uuid
from pathlib import Path

from .config import ARTIFACT_STEM, REPO_ROOT
from .provenance import file_sha256, source_fingerprint

PREVIEW_TIMEOUT_SECONDS = 300
PROCESS_STOP_TIMEOUT_SECONDS = 5


def locate_appimage(explicit=None):
    configured = explicit or os.environ.get("FREECAD_APPIMAGE")
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"FreeCAD AppImage not found: {path}")
        return path
    for directory in (Path.home() / "Applications", Path.home() / "Downloads"):
        candidates = sorted(directory.glob("*FreeCAD*.AppImage"), reverse=True)
        if candidates:
            return candidates[0].resolve()
    raise FileNotFoundError(
        "Set FREECAD_APPIMAGE or --freecad-appimage to your installed AppImage. "
        "For another FreeCAD installation, open build_gondola.FCMacro / preview_gondola.FCMacro in FreeCAD."
    )


@contextlib.contextmanager
def mounted_appimage(appimage):
    process = subprocess.Popen(
        [str(appimage), "--appimage-mount"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=20):
                raise RuntimeError(
                    "FreeCAD AppImage mount did not return a path within 20 seconds."
                )
            mount = Path(process.stdout.readline().strip())
        if not mount.is_absolute() or not (mount / "AppRun").is_file():
            raise RuntimeError(
                "Could not mount FreeCAD AppImage; check local FUSE/AppImage support."
            )
        yield mount
    finally:
        process.terminate()
        try:
            process.wait(timeout=PROCESS_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        finally:
            process.stdout.close()
            process.stderr.close()


def _stop_preview_process(process):
    """Stop the dedicated GUI session, including children started by AppRun."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=PROCESS_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _run_preview_process(args, env):
    process = subprocess.Popen(args, cwd=REPO_ROOT, env=env, start_new_session=True)
    try:
        return process.wait(timeout=PREVIEW_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _stop_preview_process(process)
        raise RuntimeError(
            f"FreeCAD preview did not finish within {PREVIEW_TIMEOUT_SECONDS} seconds. "
            "Check that a graphical display is available and inspect the FreeCAD output."
        ) from error
    except BaseException:
        _stop_preview_process(process)
        raise


def _verify_preview_state(output_dir, run_id, fingerprint):
    """Require fresh evidence from this invocation, never an earlier success."""
    try:
        state = json.loads((output_dir / "preview_state.json").read_text())
        if not isinstance(state, dict) or state.get("run_id") != run_id:
            raise RuntimeError(
                "FreeCAD preview did not write a result for this invocation."
            )
        if state.get("passed") is not True:
            error = str(state.get("error") or "FreeCAD preview did not finish.")
            raise RuntimeError(
                f"{error.strip().splitlines()[-1]} See {output_dir / 'preview_state.json'}."
            )
        if (
            state.get("source_fingerprint") != fingerprint
            or source_fingerprint() != fingerprint
        ):
            raise RuntimeError(
                "Source changed during preview; rebuild and render again."
            )
        cad_hash = file_sha256(output_dir / (ARTIFACT_STEM + ".FCStd"))
        if state.get("source_sha256") != cad_hash:
            raise RuntimeError(
                "Saved CAD changed during preview; render and validate again."
            )
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "FreeCAD preview did not write a readable result; inspect its output."
        ) from error


def run_with_freecad(command, output_dir, appimage=None, source=None):
    # AppRun executes from REPO_ROOT; resolve caller-relative paths before changing cwd.
    output_dir = Path(output_dir).expanduser().resolve()
    source = Path(source).expanduser().resolve() if source is not None else None
    with mounted_appimage(locate_appimage(appimage)) as mount:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            (str(REPO_ROOT), str(mount / "usr" / "lib"))
        )
        env["GONDOLA_OUTPUT_DIR"] = str(output_dir)
        if command == "preview":
            run_id = uuid.uuid4().hex
            fingerprint = source_fingerprint()
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "preview_state.json").write_text(
                json.dumps({"passed": False, "status": "starting", "run_id": run_id})
                + "\n"
            )
            env["GONDOLA_CLOSE_AFTER_PREVIEW"] = "1"
            env["GONDOLA_PREVIEW_RUN_ID"] = run_id
            args = [str(mount / "AppRun"), str(REPO_ROOT / "preview_gondola.FCMacro")]
            try:
                returncode = _run_preview_process(args, env)
                if returncode:
                    raise RuntimeError(
                        f"FreeCAD preview exited with status {returncode}; inspect its output."
                    )
                _verify_preview_state(output_dir, run_id, fingerprint)
            except BaseException as error:
                # A close failure or timeout must invalidate even a result that
                # the GUI wrote just before it stopped responding.
                state_path = output_dir / "preview_state.json"
                try:
                    state = json.loads(state_path.read_text())
                except (OSError, ValueError):
                    state = {}
                if not isinstance(state, dict) or state.get("run_id") != run_id:
                    state = {}
                state.update(
                    passed=False,
                    status="failed",
                    run_id=run_id,
                    error=state.get("error") or str(error) or "Preview interrupted.",
                )
                (output_dir / "preview_state.json").write_text(
                    json.dumps(state, indent=2) + "\n"
                )
                raise
            return 0
        else:
            args = [
                str(mount / "AppRun"),
                "python",
                "-m",
                "gondola",
                "--inside-freecad",
                "--output-dir",
                str(output_dir),
                command,
            ]
            if source:
                args.extend(["--source", str(source)])
        completed = subprocess.run(args, cwd=REPO_ROOT, env=env)
        if completed.returncode:
            return completed.returncode
        return 0
