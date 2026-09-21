# AI agent operating contract

This document governs agent work on the indoor LTA blimp gondola. Keep executable
contracts, native CAD metadata and generated artifacts consistent. Dimensions,
purchase quantities and manufacturer evidence belong in their source modules;
do not maintain a second BOM or dimensional specification here.

## Source authorities

| Concern | Authority |
|---|---|
| Scope, selected equipment, manufacturing decision, inventory, wiring purchases and unresolved interfaces | `gondola/design_contract.py`; inspect with `python3 -m gondola status` |
| Published device holes, connectors, sources and explicit unknowns | `gondola/parts/mounting_interfaces.py`; retained evidence in `references/` |
| Rail, shoes, clamp interfaces and propulsion | `gondola/parts/rail.py`, `propulsion.py`, `fastener_spec.py` |
| Equipment carriers, battery placement, device envelopes and wiring allowances | `gondola/parts/equipment_mounts.py`, `equipment_envelopes.py`, `wiring_clearance.py` |
| Shared optical stack, manual adjustment and moving sensor frame | `gondola/parts/stack_interface.py`, `optical_mount.py`, `optical_sensor.py` |
| Purchased mechanism specifications and source evidence | `gondola/parts/metric_hardware.py`; quantities in `design_contract.py` |
| Native hierarchy, controls and metadata | `gondola/assembly.py`, `cad.py`, `parts/equipment_metadata.py` |
| Unique printed-part exports | `gondola/manufacturing.py` |
| Hardware material identity, BOM grouping and per-SKU evidence | `gondola/procurement.py` |
| Current mass accounting and exclusions | `gondola/mass_budget.py` |
| Geometry, motion, service, optics, exports and pinned comparison | `gondola/validation/`, `tests/fixtures/` |
| Artifact identity, source hashes and release package gates | `gondola/config.py`, `provenance.py`, `bundle.py` |

## Design constraints

- Scope includes two main propulsors with independent bounded ±150° tilt, their
  two servos, FC, battery, LR900-A, LinkTrack P-AS and MTF-02P. Exclude yaw
  propulsion, fins, fin servos and optional 360° configurations.
- Prioritize low mass, simple shapes and few purchased part types. The user
  accepts lower stiffness than a sub-250 g multirotor; this is not a load rating.
  Prefer stock fasteners, spacers, dampers, horns and harness parts available on
  AliExpress. Retain custom geometry where no verified stock replacement
  preserves its function. Add washers only when actual bearing geometry requires
  them; the current mechanism is washerless.
- Use Creallo PA12, with SLS preferred for the fit prototype and MJF an alternative
  subject to agreement. Keep the nominal rail length ceiling at 340 mm, general
  functional walls at least 1.5 mm and the documented 1.2 mm rail flexure exception.
  Published process sizes are screening bounds, not guaranteed one-piece capacity.
  Agree process, finish and one-piece rail acceptance; use matching coupons.
- Keep the shared shoe capture, both selectable clamp approaches, flexure root
  reliefs and rail engagement limits. Tape goes over the rail wings, not beneath
  the rail or across its running head. Test full-rail flexure and tape retention;
  short coupons do not qualify them.
- Keep compact role-specific battery and electronics carriers with integral
  shoes. Preserve published mounting axes where supported by adequate material;
  do not invent PCB bearing planes, screw lengths, thread depths or device holes.
  RS1102 mounting and the DS-M005 horn connection remain unresolved despite
  published partial dimensions. Preserve journal axial capture through the
  integral carrier cap; an open D-bore is not an equivalent washerless design.
- Preserve the 8 mm allowance beneath the full FC envelope and the connected
  wiring corridor and connector band. FC and P-AS attachment kits remain
  incomplete until actual bearing planes and purchased parts are measured.
  Use the included FC dampers; keep ESC cooling surfaces and antennas clear.
- Keep manufacturer evidence distinct from design allowances. Device envelopes,
  connector-access lanes and motor slack loops are not complete cable routes,
  verified bend radii or installed port datums. Preserve source discrepancies
  until actual evidence resolves them. Match official pinouts and supply ratings;
  matching connector family or pin count does not establish compatibility.

## Optical stack and service

The shared two-point diagonal M2 interface is a project standard, not an industry
standard. Its datums, purchased columns and supported hosts are defined by
`stack_interface.interface_contract()`. Stack loads bypass the FC PCB and dampers.
Keep one complete optical kit and move it using
`stack_interface.attach_to_host(doc.OpticalFlowModule, host)`; do not reparent
individual pieces. The default host is `design_contract.OPTICAL_STACK_HOST`.
Both supported hosts must pass clearance, optics and service checks. Matching
holes alone do not qualify another host.

`OpticalRollStage.Roll` and `OpticalPitchStage.Pitch` are bounded manual planning
controls; use `optical_mount.set_angles()` to update them together. Keep the sensor,
optical reservation and connector lane in the moving pitch frame. Align at loaded
flight trim and verify firmware yaw/position offsets. The CAD Z axis points away
from the balloon; added mass does not guarantee a vertical optical axis. Neither
active stabilization, physical angle stops nor qualified friction retention is
claimed. Validate both the full external angular bound and sampled internal
mechanism poses; report the distinction.

Disconnect leads before adjustment, device removal or module sliding. Preassemble
lower stack screws off the rail. Remove the head using its two upper screws
before lifting the underlying device; clearance checks must retain the columns
and lower fasteners. Battery placement must satisfy
`equipment_mounts.BATTERY_PLACEMENT_CONTRACT`; for larger trim changes, move the
complete carrier and recheck neighboring modules, rotors and connector reserves.

## Procurement and qualification

The generated hardware BOM covers modeled mechanism hardware only. Read its
explicitly unmodeled requirements and `design_contract.WIRING_PURCHASE_PLAN` for
additional attachment kits, harnesses and consumables; subtract included or owned
items. Manufacturer examples and AliExpress searches are not verified seller
options or supplier lots. Match material, dimensions, thread engagement and actual
usable spacer depth to `metric_hardware.PROCUREMENT_SPECS` before selection.

`design_contract.release_status()` is controlled by unresolved evidence, not by
passing CAD tests. Geometry checks do not establish strength, tightening torque,
friction retention, wear, creep, electrical compatibility or flight readiness.
`mass_budget.py` estimates current BRep volume times assumed material density;
these totals are not measured all-up mass. Preserve stated exclusions for
incomplete device mounting kits, wiring, adhesives and other unmeasured items.

## Execution and review gates

Run from the repository root with Python 3.11+. Offline checks and GitHub CI skip
FreeCAD-dependent tests; they cannot substitute for native geometry validation.
The Linux CLI uses an installed FreeCAD AppImage from `~/Applications` or
`~/Downloads`; override with `FREECAD_APPIMAGE` or `--freecad-appimage PATH`.
CAD commands need its bundled Python, Part, Mesh and MeshPart modules. Preview
also needs a graphical display. The reviewed kernel is FreeCAD 1.1.3; investigate
geometric differences when changing versions.

```sh
uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
uvx ruff==0.16.8 format --check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
python3 -m unittest discover -s tests -v
python3 -m compileall -q gondola
python3 -m gondola status
```

Run the same test suite inside FreeCAD's Python; confirm no native tests are skipped:

```sh
python3 - <<'PY'
import os
import subprocess
from gondola.config import ROOT
from gondola.runtime import locate_appimage, mounted_appimage

with mounted_appimage(locate_appimage()) as mount:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(mount / "usr/lib")))
    subprocess.run(
        [str(mount / "AppRun"), "python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT, env=env, check=True,
    )
PY
```

For changed CAD source, freeze edits and run the release sequence below. Stop on
any failure; each command must succeed before the next starts.

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola validate
python3 -m gondola compare
python3 -m gondola bundle
```

Preview saves native display properties and changes the CAD hash, so it must run
before validation and comparison. Inspect the rendered whole assembly, print
layout and optical views for both hosts. All reports and exports must describe
the exact current source and saved CAD; never copy an earlier success report.
Rebuild after CAD source changes. For an alternate output directory, put
`--output-dir PATH` before every command consistently.

Artifact schema3 preserves all shared-SKU labels and notes as lists; older
exports must be rebuilt rather than mixed with current reports.

Preserve the pinned regression fixture for refactors that do not change geometry
or native contracts. Deliberate changes require an old/new shape, placement,
control and metadata audit before updating the fixture and its checksum. Never
regenerate it merely to pass comparison or add exceptions that conceal damage.

`build/` is the default generated directory and is ignored by Git. Export only
manifest-listed print parts; equipment, purchased hardware and reservations are
not print parts. Preview must restore the configured optical host before saving.
Do not commit build trees, duplicate archives, logs or temporary mounts. GUI entry
points are `build_gondola.FCMacro` and `preview_gondola.FCMacro`.
