# AI agent operating guide

Read [HANDOFF.md](HANDOFF.md) for user requirements, decision history and known
limitations. This README covers repository navigation, edits and verification.
Both files are for AI agents, not manufacturing or assembly instructions.

## Establish the current state

1. Inspect Git status and the latest user request. Preserve unrelated edits and
   any manually changed CAD that matters before regenerating output.
2. Run `python3 -m gondola status` from the repository root. Read the selected
   revision, profiles and unresolved interfaces in the source contracts below.
3. Read the relevant retained evidence and revision review. Documentation and
   source describe intended design; neither proves received-part fit. Resolve
   contradictions explicitly instead of silently treating one as measured truth.

Later user decisions supersede this handoff. Current geometry is an implementation,
not a permanent constraint. Do not restore historical choices just because an
old reference, fixture or shopping list contains them.

## Source map

| Concern | Primary repository location |
| --- | --- |
| Scope, revision, layout, manufacturing basis, inventory and unresolved interfaces | [design.py](gondola/contracts/design.py) |
| Selected FC and published equipment interfaces | [equipment_interfaces.py](gondola/contracts/equipment_interfaces.py) |
| Navigation/radio alternatives and optical selection | [equipment_options.py](gondola/contracts/equipment_options.py), [optical_sensors.py](gondola/contracts/optical_sensors.py) |
| Selected gears, bought hardware and nominal fastener envelopes | [drive.py](gondola/contracts/drive.py), [hardware.py](gondola/contracts/hardware.py), [fasteners.py](gondola/contracts/fasteners.py) |
| Geometry and native hierarchy/controls | [parts/](gondola/parts/), [assembly.py](gondola/assembly.py), [cad.py](gondola/cad.py) |
| Print exports, purchases and estimated mass | [print_export.py](gondola/print_export.py), [procurement.py](gondola/procurement.py), [mass_budget.py](gondola/mass_budget.py) |
| Checks, pinned regression baseline and artifact identity | [validation/](gondola/validation/), [tests/](tests/), [config.py](gondola/config.py), [provenance.py](gondola/provenance.py), [bundle.py](gondola/bundle.py) |
| Commands and FreeCAD runtime | [cli.py](gondola/cli.py), [freecad_runtime.py](gondola/freecad_runtime.py) |

Read references according to the changed interface; their revision/date matters:

- Drive and purchasing: [selection](references/drive_selection_review.md),
  [seller gear evidence](references/kailash_gears_selected_evidence.md),
  [cart decisions](references/cart_adaptation_review.md),
  [bearing retention and purchased-horn coupling](references/retention_review.md).
- Structure and wiring: [layout](references/layout_and_wiring_review.md),
  [rail joint](references/rail_joint_review.md), [rail fit](references/rail_fit_review.md),
  [shape rationale](references/shape_simplification_review.md).
- Electronics: [controller](references/controller_selection_review.md),
  [navigation](references/navigation_module_compatibility.md),
  [radio](references/radio_module_compatibility.md),
  [optical sensor](references/optical_sensor_compatibility.md).

Do not copy full dimension or purchase tables into this README. A source contract
is the implementation's authority, while retained drawings support or qualify its
inputs. Catalog claims, design allowances and physical measurements remain distinct.

## Editing and verification boundaries

- Keep geometry, native properties, motion controls, BOM and reservations consistent.
  Use shared oriented datums, including the servo envelope, carrier orientation and
  FC orientation. Transform local clamp/tool directions into the assembly frame.
  Do not duplicate interface dimensions in unrelated geometry helpers.
- Preserve the deliberately removable paired-servo/input-drive module. The current
  gear spacing is fixed; another servo or ratio requires a complete interface and
  mechanism review. Editing a saved ratio property does not regenerate gear teeth.
  Check seating and the actual ordered removal path, not just separated end poses.
- Preserve bounded tilt without endpoint wraparound. Check coupled gearing,
  permitted axial travel, retained contact and continuous rotation bounds where
  applicable. Label sampled checks as sampled; distinguish intentional bearing,
  gear and stop contacts from unexpected interference.
- The [selected purchased horn](references/retention_review.md#selected-replacement-horn--2026-09-25)
  uses factory M1.6 threads, an integral open root saddle and round/slot assembly
  clearance. Export the installed adapter solid; no horn-drilling blank or jig
  remains. Preserve user-accepted X06 compatibility and confirmed threads.
  Missing axial seating/root concentricity remain explicit prototype envelopes.
  Adjustment is before tightening, not intentional operating looseness. Recheck
  front screw and gear removal paths when changing the coupling. Keep shaft
  grip separate from axial/bearing retention.
- Rail and bearing coupons address finished fit and retention. Nominal dimensions
  and prescribed latch release motion do not establish insertion force, elastic
  recovery, shield clearance, creep or fatigue. Do not close an unverified bearing
  retention path by assuming press fit or adding the rejected shield-contact bush.
- Apply the manufacturing size rule before and after print rotation. Check local
  functional sections and powder-removal access. Supplier envelopes and minimum
  walls are screening inputs, not proof of one-piece acceptance or finished fit.
- Check cable/connector reservations against physical parts and other reservations.
  Motor leads move; servo-case leads do not. A reserved loop or neutral straight-line
  distance is not an installed harness, cut length or flexible-wire sweep proof.
  Recheck routing, strain relief and service access after layout changes.
- Select one device per navigation, radio and optical region. Persistent selection
  changes require rebuilding all affected artifacts; temporary profile probes are
  not released configurations. Some native IDs retain older device names: inspect
  the selected model/profile properties and labels instead of inferring the device
  from its object ID. Count alternative equipment only when selected.
- Use `stack_interface.attach_to_host()` for optical-host changes and
  `optical_mount.set_angles()` for its manual alignment. Verify both supported hosts,
  sensor profiles, fields of view, registration allowances and service paths.
  Sensor-to-tray adhesive and host-to-tower foot clamps are different interfaces.
  Actual pointing stability, cable slack and firmware orientation remain checks.
- Preserve unresolved evidence such as FC input voltage, actual dampers, antenna
  placement and adhesive contact. Missing mass is unknown, not zero. Geometric
  success alone must not change `design.release_status()` to physical qualification.
  Check its unresolved-interface list for unmodeled parts and load limits; a whole-
  assembly check covers only the modeled geometry and declared bounds.

The source fingerprint covers `gondola/**/*.py` and root `.FCMacro` files only.
It excludes documentation, retained evidence, tests and Blender tools. Matching
hashes are necessary for artifact identity but do not prove all supporting evidence
is current. Reassess affected conclusions when that evidence changes.

## Checks and generated outputs

For wording-only changes, review accuracy, local links and `git diff --check`;
do not regenerate CAD merely to update prose. If a documentation correction changes
a design input or exposes an implementation error, assess and validate that change.

For source changes, use Python 3.11+ from the repository root:

```sh
uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
uvx ruff==0.16.8 format --check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
python3 -m unittest discover -s tests -v
python3 -m compileall -q gondola
```

Offline tests skip FreeCAD-dependent cases. Before accepting changed CAD artifacts,
run the native suite and confirm no skips. The runtime locates a Linux FreeCAD
AppImage in `~/Applications` or `~/Downloads`; `FREECAD_APPIMAGE` overrides it.
The reviewed runtime is FreeCAD 1.1.3; investigate kernel-dependent differences when
changing versions. Preview requires a graphical display.

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

Preserve the pinned fixture during behavior-preserving refactors. Intentional
geometry/native-contract changes require an independent old/new shape, placement,
control and metadata review before updating the fixture and checksum in `config.py`.
Do not regenerate the fixture merely to pass comparison or hide a failed check.

Freeze source changes and run the artifact pipeline sequentially, stopping on failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola validate
python3 -m gondola compare
python3 -m gondola bundle
```

Build/preview overwrite generated output. Preview saves display properties and
changes the CAD hash, so it precedes validation/comparison. Inspect assembly,
print layout and both optical-host views; restore the configured host before saving.
Record final checks against that source and saved CAD in the revision review.
For another directory, pass `--output-dir PATH` before every subcommand consistently;
the CLI also accepts `--freecad-appimage PATH` before the subcommand.

`build/gondola.FCStd` is the default generated assembly. The fixture selected by
`config.py` is a regression comparison baseline, not an alternative manufacturing
assembly. Export only manifest-listed print parts. `build/`, logs and temporary
audit files are not committed and may be absent in another environment. Keep retained
evidence and the revision review in Git; do not rely on `/tmp` as the sole record.
GUI entry points are `build_gondola.FCMacro` and `preview_gondola.FCMacro`.

## Blender derivative

After native validation, `python3 tools/blender_review/run.py --render-stills`
generates `build/blender_review/cad_review.blend`; add `--open` when opening it is
requested. The reviewed setup used Blender 5.2.2. Verify the derivative after tool
or Blender changes, preserving its source/CAD identities and `verification.json`.

The verifier compares evaluated Blender transforms with sampled native poses.
This is prescribed rigid motion, not collision, dynamics, wire, friction or strength
simulation. Optical host transfer and powered alignment are not simulated.
The display is rotated as a whole so neutral sensor aim points down; native CAD
coordinates are unchanged. Blender-only edits do not by themselves justify promoting
the CAD regression fixture.
