# AI agent operating contract

Keep source contracts, native CAD metadata and generated artifacts consistent.
Do not duplicate dimensions, purchase quantities or manufacturer evidence here.

## Authorities

- `gondola/contracts/` holds data independent of FreeCAD: `design.py` for scope,
  decisions, inventory and unresolved interfaces; `equipment_interfaces.py` for
  published device evidence; `hardware.py` for purchase specifications, shaft
  preparation validation and shared CAD/BOM field names; `fasteners.py` for
  shared nominal dimensions; `drive.py` for the finite gear configurations and
  source-authoritative `SELECTED_DRIVE`.
  Inspect project status with `python3 -m gondola status`.
- Read `references/drive_selection_review.md` before drivetrain changes or
  purchasing. `SELECTED_DRIVE` identifies the selected 48T/16T mechanism;
  `references/kailash_gears_selected_evidence.md` retains its seller evidence.
  `references/cart_adaptation_review.md` records cart choices and remaining
  purchases; current build quantities belong to `contracts/design.py`.
  `references/retention_review.md` describes inward-loaded bearing cups,
  integral outer shoulders, bought inner-ring spacers and the staged assembly
  path. Preserve separate shaft grip and broad carrier/frame axial stops.
  The optical seats use direct M2 clamps; the archived
  latch review records a superseded trial, not an assembly instruction.
  `references/rail_joint_review.md` explains the solid rail-head clamp,
  continuous bearing-post roots and short-arm L-key access. Keep wiring
  outside those roots; do not restore long tool tunnels through them.
  `references/shape_simplification_review.md` records the optical portal and
  open paired-servo support, horn adapter and straight P-AS arm; preserve their locating faces, load paths and functional service openings.
  `references/rail_fit_review.md` distinguishes the matched T-head fit from
  relieved nonlocating surfaces. Qualify the existing coupons before full prints;
  do not claim raw powder-bed tolerance guarantees hand insertion or retention.
- `gondola/parts/` builds printed parts, purchased hardware, equipment envelopes
  and wiring reserves. `references/` retains primary evidence; preserve it.
- `gondola/assembly.py` and `cad.py` define native hierarchy and controls;
  `print_export.py`, `procurement.py` and `mass_budget.py` define export accounting.
- `gondola/validation/` and `tests/fixtures/` define regression checks;
  `validation/manufacturing.py` owns wall measurements and process allowances;
  `validation/wiring.py` owns reserve geometry and declared access margins.
  `config.py`, `provenance.py` and `bundle.py` enforce artifact identity.
- `cli.py` dispatches commands; `freecad_runtime.py` manages the AppImage process.

## Editing rules

- Prioritize simple integral geometry, forgiving noncritical interfaces and few
  purchased part types for this indoor LTA gondola; modest mass increases are
  accepted when they simplify assembly. Lower stiffness than a sub-250 g multirotor is accepted;
  this is not a strength qualification. First integrate parts without a necessary
  separation, make them printable, then optimize shape. Prefer verified stock
  components with few fastener variants and no unnecessary washers. Retained
  assembly, motion and replacement interfaces are explained in `design.py`;
  reassess those reasons rather than preserving the part count by default.
  Apply its part-size ceiling before and after export rotation. Follow the
  supplier's powder-bed guidance and agreed unfilled PA12 process/finish; do not assume
  FDM support rules or an SLS/MJF process preference.
- Existing geometry, shaft diameters and purchased-part selections are not
  constraints. Redesign them when the complete assembly improves in mass,
  simplicity, fit or serviceability. Compare complete torque/retention paths;
  a lighter shaft or gear alone does not establish a better assembly.
- Model only supported interfaces. Do not invent device holes, bearing planes,
  thread depths, mounting kits, cable datums or electrical compatibility.
  Preserve source discrepancies and explicit design allowances.
- Check connector handling and wire reserves against both physical parts and
  other reserved spaces. Keep sampled attitude checks distinct from continuous
  bounds; nominal clearances do not verify actual plugs, latches or harnesses.
- Preserve the native geared input/output expressions and bounded, non-wrapping
  tilt controls. Validate gear contact, coupled motion and bearing/fastener
  retention together. Purchased gear profiles are reference geometry, never
  printable replacements; shaft and bearing fits require physical trials.
  Check continuous rotation envelopes near fasteners as well as sampled poses.
  Include permitted axial travel in clearance and gear-face engagement budgets;
  distinguish deliberate bearing, gear and axial-stop contact from collisions.
- The selected plain-bore driver gears mount on short nominal-3mm input stubs,
  retained in open printed clamping adapters on bought KST horns. Preserve the short root/end locating faces and verify their registration from saved geometry; bolt-hole clearance alone does not establish concentricity. The prepared-horn
  purchase key requires enlarging only the sourced tip hole for the direct
  M1.6 adapter joint; do not describe that modification as a factory feature
  or infer strength from clearance tests. Keep the original horn spline and
  retaining screw; do not invent a printed spline or restore
  the former hollow journal for a 7 mm gear bore. Only output axes use external
  bearings. One removable bridge carries both servos in a common central wall
  and retains their complete input drives. A central seat supports that wall
  directly; two outer mounting seats and fixed datums locate the module on the
  common output-bearing frame. Replace the
  bridge and the affected transmission parts for a ratio change; only the
  selected ratio is currently supported. A different servo requires its own
  verified interface. Check seated contact and the ordered module
  removal path while retaining the output shafts, bearings and motor carriers.
  Rebuild geometry, controls and BOM together.
  Gear spacing remains fixed; optical mounting clearances do not authorize slotted
  gear supports or an unsupported GUI ratio-only property.
  Preserve each gear's catalogued bore in CAD and purchasing. Check actual mesh,
  adapter concentricity/retention and servo output loading; printed nominal
  dimensions are not guaranteed fits. Changing `SELECTED_DRIVE` requires the complete
  fixture audit and release checks below.
- M2 kit screws use explicit design head envelopes until measured. Do not label
  them DIN912/A2 or infer their mass from the envelope as a measured value.
  The rail hex-nut
  seat requires its declared finished-fit range and coupon checks; raw printing
  tolerance does not guarantee capture. Ordinary bolt tips must be checked
  before pressing the rail; they are not certified DIN913 flat points.
- Cut the selected nominal-3mm rod to the encoded preparation keys. Keep output
  bearing journals round; full-length flats belong only on input stubs. Generic
  selected bearings are not certified ISC parts; retained ISC evidence is a
  dimensional comparison, not the purchased lot's mass or fit qualification.
- Change the complete optical kit's host through
  `stack_interface.attach_to_host()` and its angles through
  `optical_mount.set_angles()`. Both supported hosts must pass clearance, optics
  and service checks, including integral legs/feet and complete tower removal.
  Seat both broad feet directly before tightening their M2 clamps. Clearance
  holes allow assembly registration, not operating play; validate their full
  registration envelope on both hosts. Check actual fastener bearing faces,
  print flatness, clamp friction and PA12 creep. Reject rocking or slip before
  accepting sensor alignment. Detach the host carrier for bench access to the
  underside screws; the unmodeled balloon may obstruct an in-place tool.
  Support the tower, remove both foot nuts and withdraw the screws downward
  before lifting it. Reinstall the carrier, verify retention and re-trim. Positive sensor Z points away from the balloon;
  consider loads in both axial directions. Keep reservations in the moving
  sensor frame.
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
