#!/usr/bin/env python3
"""Build a Blender review from the existing saved CAD, without regenerating it."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gondola.freecad_runtime import locate_appimage, mounted_appimage  # noqa: E402


def locate_blender(explicit=None):
    if explicit:
        executable = shutil.which(str(Path(explicit).expanduser()))
        if executable:
            return Path(executable).resolve()
        raise FileNotFoundError(
            f"Blender executable not found or not executable: {explicit}"
        )
    executable = shutil.which("blender")
    if executable:
        return Path(executable).resolve()
    for candidate in sorted(
        (Path.home() / "Applications").glob("blender-*/blender"), reverse=True
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise FileNotFoundError(
        "Blender was not found on PATH or in ~/Applications/blender-*/blender. "
        "Install Blender or pass --blender /path/to/blender."
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cad", type=Path, default=REPO_ROOT / "build" / "gondola.FCStd"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "build" / "blender_review"
    )
    parser.add_argument("--blender", help="Blender executable path or command")
    parser.add_argument(
        "--render-stills", action="store_true", help="Also render review stills"
    )
    parser.add_argument(
        "--open", action="store_true", help="Open the finished review in Blender"
    )
    return parser.parse_args(argv)


def run(args):
    cad = args.cad.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    scripts = Path(__file__).resolve().parent
    exporter = scripts / "export_cad.py"
    builder = scripts / "build_scene.py"
    verifier = scripts / "verify_scene.py"
    for path, label in (
        (cad, "Saved CAD"),
        (exporter, "FreeCAD exporter"),
        (builder, "Blender scene builder"),
        (verifier, "Blender scene verifier"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    blender = locate_blender(args.blender)
    appimage = locate_appimage()
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = output_dir / "cad_review.json"
    blend = output_dir / "cad_review.blend"
    print(f"Exporting saved CAD: {cad}", flush=True)
    with mounted_appimage(appimage) as mount:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT), str(mount / "usr/lib")))
        subprocess.run(
            [
                str(mount / "AppRun"),
                "python",
                str(exporter),
                "--cad",
                str(cad),
                "--output",
                str(exported),
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
        )
    if not exported.is_file():
        raise RuntimeError(f"FreeCAD exporter did not create {exported}")
    command = [
        str(blender),
        "--background",
        "--python-exit-code",
        "1",
        "--python",
        str(builder),
        "--",
        "--input",
        str(exported),
        "--output",
        str(blend),
    ]
    if args.render_stills:
        command.extend(("--render-stills", str(output_dir / "stills")))
    print(f"Building Blender review: {blend}", flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)
    if not blend.is_file():
        raise RuntimeError(f"Blender scene builder did not create {blend}")
    verification = output_dir / "verification.json"
    subprocess.run(
        [
            str(blender),
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str(verifier),
            "--",
            "--input",
            str(exported),
            "--blend",
            str(blend),
            "--output",
            str(verification),
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    if json.loads(verification.read_text()).get("passed") is not True:
        raise RuntimeError(f"Blender review verification failed: {verification}")
    if args.open:
        log_path = output_dir / "blender_gui.log"
        with log_path.open("wb") as log:
            subprocess.Popen(
                [str(blender), str(blend)],
                cwd=REPO_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(f"Opened Blender; startup log: {log_path}", flush=True)
    return blend


def main(argv=None):
    args = parse_args(argv)
    try:
        blend = run(args)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Blender review failed: {error}", file=sys.stderr)
        return 1
    print(f"Review ready: {blend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
