# AI agent operating contract

Keep source contracts, native CAD metadata and generated artifacts consistent.
Do not duplicate dimensions, purchase quantities or manufacturer evidence here.

## Authorities

- `gondola/contracts/` holds data independent of FreeCAD: `design.py` for scope,
  decisions, inventory and unresolved interfaces; `equipment_interfaces.py` for
  published device evidence; `hardware.py` for purchase specifications and shaft
  order validation; `fasteners.py` for shared nominal dimensions.
  Inspect project status with `python3 -m gondola status`.
- `gondola/parts/` builds printed parts, purchased hardware, equipment envelopes
  and wiring reserves. `references/` retains primary evidence; preserve it.
- `gondola/assembly.py` and `cad.py` define native hierarchy and controls;
  `print_export.py`, `procurement.py` and `mass_budget.py` define export accounting.
- `gondola/validation/` and `tests/fixtures/` define regression checks;
  `validation/manufacturing.py` owns wall measurements and process allowances.
  `config.py`, `provenance.py` and `bundle.py` enforce artifact identity.
- `cli.py` dispatches commands; `freecad_runtime.py` manages the AppImage process.

## Editing rules

- Prioritize low mass, simple geometry and few purchased part types for this
  indoor LTA gondola. Lower stiffness than a sub-250 g multirotor is accepted;
  this is not a strength qualification. Prefer verified stock components.
- Model only supported interfaces. Do not invent device holes, bearing planes,
  thread depths, mounting kits, cable datums or electrical compatibility.
  Preserve source discrepancies and explicit design allowances.
- Preserve the native geared input/output expressions and bounded, non-wrapping
  tilt controls. Validate gear contact, coupled motion and bearing/fastener
  retention together. Purchased gear profiles are reference geometry, never
  printable replacements; shaft and bearing fits require physical trials.
- Change the complete optical kit's host through
  `stack_interface.attach_to_host()` and its angles through
  `optical_mount.set_angles()`. Both supported hosts must pass clearance, optics
  and service checks. Keep reservations in the moving sensor frame.
- Passing geometry tests does not resolve physical qualification or change
  `contracts.design.release_status()`. Keep estimated mass exclusions and
  unresolved interfaces explicit in generated outputs.
- Preserve the pinned fixture during refactors. Intentional geometry or native
  contract changes require an old/new shape, placement, control and metadata
  audit before updating the fixture and checksum. Never regenerate it merely
  to pass comparison or add exceptions that conceal damage.

## Checks and release

Run from the repository root with Python 3.11+. Offline tests and GitHub CI skip
FreeCAD-dependent tests. Native CAD checks use the Linux FreeCAD AppImage in
`~/Applications` or `~/Downloads`; override with `FREECAD_APPIMAGE` or
`--freecad-appimage PATH`. The reviewed kernel is FreeCAD 1.1.3; investigate
geometry differences after version changes. Preview needs a graphical display.

```sh
uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
uvx ruff==0.16.8 format --check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
python3 -m unittest discover -s tests -v
python3 -m compileall -q gondola
python3 -m gondola status
```

Run the native suite and confirm no tests are skipped:

```sh
python3 - <<'PY_NATIVE'
import os
import subprocess
from gondola.config import REPO_ROOT
from gondola.freecad_runtime import locate_appimage, mounted_appimage

with mounted_appimage(locate_appimage()) as mount:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT), str(mount / "usr/lib")))
    subprocess.run(
        [str(mount / "AppRun"), "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=REPO_ROOT, env=env, check=True,
    )
PY_NATIVE
```

Freeze source edits before releasing. Run sequentially; stop on any failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola validate
python3 -m gondola compare
python3 -m gondola bundle
```

Preview changes the saved CAD hash, so it precedes validation and comparison.
Inspect assembly, print layout and optical views for both hosts. Preview must
restore the configured host before saving. Reports and exports must match the
current source and saved CAD; rebuild after source changes, never reuse earlier
success reports. For alternate output paths, pass `--output-dir PATH` before
every command consistently.

Export only manifest-listed print parts. Keep generated `build/`, archives,
logs and temporary mounts out of Git. GUI entry points are
`build_gondola.FCMacro` and `preview_gondola.FCMacro`.
