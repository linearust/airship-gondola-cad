# AI agent operating guide

Read [HANDOFF.md](HANDOFF.md) for user requirements, decision history and known
limitations. This README covers repository navigation, edits and verification.
Both files are for AI agents, not manufacturing or assembly instructions.

Active direction (2026-09-28), revision BB: square printed carriers with a
quarter-turn-symmetric array of fixed FC holes and adjustable slots, plus a
compact one-axis optical pedestal attached directly to the common outer slots.
The rail and deliberately separate servo/propulsion modules remain in use.
Read [the design review](references/square_mount_review.md) and the
[BB verification record](references/square_mount_verification.json) before claiming verification. AY restoration is historical;
its checks do not certify this change. Bought-carbon-plate rail architectures
remain superseded. Normal purchased gears, bearings and fasteners remain selected.

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
| Navigation alternatives, selected radio and optical selection | [equipment_options.py](gondola/contracts/equipment_options.py), [optical_sensors.py](gondola/contracts/optical_sensors.py) |
| Selected gears, bought hardware and nominal fastener envelopes | [drive.py](gondola/contracts/drive.py), [hardware.py](gondola/contracts/hardware.py), [fasteners.py](gondola/contracts/fasteners.py) |
| Horn alternatives and optional power boards | [servo_horns.py](gondola/contracts/servo_horns.py), [power_options.py](gondola/contracts/power_options.py) |
| Shared plate, mounting slots, optional power portal and compact optical attachment | [equipment_mounts.py](gondola/parts/equipment_mounts.py), [mounting_slots.py](gondola/parts/mounting_slots.py), [stack_interface.py](gondola/parts/stack_interface.py), [optical_interface.py](gondola/parts/optical_interface.py) |
| Geometry and native hierarchy/controls | [parts/](gondola/parts/), [assembly.py](gondola/assembly.py), [cad.py](gondola/cad.py) |
| Print exports, purchases and estimated mass | [print_export.py](gondola/print_export.py), [procurement.py](gondola/procurement.py), [mass_budget.py](gondola/mass_budget.py) |
| Checks, pinned regression baseline and artifact identity | [validation/](gondola/validation/), [tests/](tests/), [config.py](gondola/config.py), [provenance.py](gondola/provenance.py), [bundle.py](gondola/bundle.py) |
| Commands and FreeCAD runtime | [cli.py](gondola/cli.py), [freecad_runtime.py](gondola/freecad_runtime.py) |

Read references according to the changed interface; their revision/date matters:

- Drive and purchasing: [selection](references/drive_selection_review.md),
  [seller gear evidence](references/kailash_gears_selected_evidence.md),
  [cart decisions](references/cart_adaptation_review.md),
  [bearing retention](references/retention_review.md),
  [three-horn compatibility](references/servo_horn_compatibility.md).
- Structure and wiring: [layout](references/layout_and_wiring_review.md),
  [universal carriers](references/universal_carrier_review.md),
  [Holybro payload-plate reference](references/holybro_x500_plate_review.md),
  [rail joint](references/rail_joint_review.md), [rail fit](references/rail_fit_review.md),
  [shape rationale](references/shape_simplification_review.md).
- Electronics: [controller](references/controller_selection_review.md),
  [navigation](references/navigation_module_compatibility.md),
  [radio](references/radio_module_compatibility.md),
  [optical sensor](references/optical_sensor_compatibility.md),
  [optional power](references/power_module_compatibility.md).

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
- The three retained 4 mm/15T horn drawings share one open slotted adapter.
  Use the selected per-side profile; the two sides may differ. Preserve factory
  spline and hole axes, actual root seating and the declared profile-specific
  fastener/preparation route. Small pilot holes are not factory M1.6 threads.
  Slot freedom is for alignment before clamping, never deliberate running slip.
  Recheck all horn profiles, reverse hardware where applicable, screw access,
  servo case clearance, loaded retention and the complete service order.
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
- Select one navigation and optical device; the onboard radio is LR24-F-Mini only.
  Persistent selection changes require rebuilding all affected artifacts;
  temporary profile probes are not released configurations. Navigation and optical
  native IDs retain older device names: inspect the selected model/profile
  properties and labels instead of inferring the device from its object ID.
  Count alternative equipment only when selected.
- Battery, FC and navigation use three copies of `UniversalEquipmentCarrier`.
  Its square plate and complete opening array are symmetric under 90-degree
  rotation and X/Y reflection; the integral rail shoe and clamp are directional.
  `mounting_slots.py` defines the common adjustment coverage. Preserve continuous
  lands, fixed FC bearing annuli, P-AS slot seats and the declared adhesive patches.
  The P-AS/navigation datum has a small Y offset so its actual two holes use the
  symmetric 23 mm slot pattern. Do not reintroduce asymmetric device-only bores.
- The optional power deck shares the plate template but retains its own portal.
  Optical and power feet use common outer slots directly. Their geometries and
  registration bounds differ: `optical_interface.py` owns the compact optical
  foot; `stack_interface.py` owns the optional power portal. Do not reuse a
  circular-hole float model for the slotted host without deriving its bounds.
- The Mini sits off to one side of the navigation plate's underside, with its
  body rotated 90 degrees and offset to leave both rail-clamp approaches and
  optional-power foot service paths clear. Preserve the
  separate body/adhesive datums and connector orientation together. Its smaller
  continuous tape allocation is available material, not qualified retention.
  Use `wiring_reserves.parent_name()` for reservation ownership; a matching world
  position cannot replace attachment to the correct movable carrier.
  Actual balloon curvature, plugged height and adhesive retention are unverified.
  Remove the carrier for bench service; rail tape wings are not a qualified
  electronics adhesive face. The accessory carrier is not a qualified optical host.
- Use `optical_interface.attach_to_host()` for optical-host changes and
  `optical_mount.set_pitch()` for the single Y-axis adjustment. There is no roll
  stage. This assumes a rail on the balloon's lower centreline and corrects only
  longitudinal curvature. Check both host candidates and both sensor profiles,
  retaining rejected combinations in the report; the selected installation must
  pass its full optical, connector, registration and removal screens.
  The tray is adhesively attached to the sensor; the foot and pivot are clamped.
  Manual alignment does not establish self-levelling or loaded pointing stability.
  Without optional power, P-AS and MG-A01 permit either host. A directly attached
  MG-F10-A helix permits the battery optical host only: the FC-host sensor field
  intersects its reserved space. A remote antenna location remains unmodeled.
  Optional power can further restrict the optical-host choice; use the permitted
  combinations in its report, not the plate's shared hole pattern.
- Common mechanical stack spacing does not certify every payload/host pairing.
  The optical and power supports have different local datums and
  cannot share one host at the same time. Keep baseline mass/BOM separate from
  optional power exports. The tether option uses one BEC12S-PRO at 8 V,
  feeding both FC/main power and the SVPDB-8S input; the latter supplies 5 V
  to servos. All downstream demand shares the upstream BEC's 5 A output
  rating, including conversion losses; installed load/thermal margin is unknown.
  Neither board has a confirmed mechanical hole pattern: use insulating contact
  and straps wrapped around the existing structure,
  preserving electrical pads, cooling and connector access. General plate holes
  are project fastening provisions, not evidence of device-specific compatibility.
  Keep the small optical tray as an uninterrupted adhesive pad. MTF-02P has no
  confirmed mounting pattern; MTF-01P's published holes are deliberately unused.
  Unverified straps near their apertures/connectors can obstruct the moving head.
  External straps do not establish the tether's installed route or rated anchor.
  Tether motion/loads and installation electrical/thermal performance remain unverified.
- Omit dedicated cable-tie holes, slots and tie-only tabs. The user wraps Velcro
  and ties around existing members. Common spare module-hole patterns are a
  separate requested feature: retain confirmed device holes and record each
  mounting pattern's pitch, slot or bore dimensions and local datum. Spare holes
  do not imply simultaneous devices, a selected fastener stack or verified adhesive retention.
  Current non-use alone is not a reason to delete these requested provisions.
  The common array keeps four fixed FC bores and sixteen slots, including the
  two P-AS axes and support-foot interfaces. Exact patterns, widths and datums
  live in source. It is not a universal industry breadboard or a complete X500
  interface. Existing M2 heads do not automatically fit M3-width slots. No extra
  baseline washers are selected.
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

Build/preview overwrite generated output. Preview saves display properties in the
main and optional power CAD, changing their hashes, so it precedes validation/comparison. Inspect assembly,
print layout and both optical-host views; restore the configured host before saving.
Record final checks against that source and saved CAD in the revision review.
For another directory, pass `--output-dir PATH` before every subcommand consistently;
the CLI also accepts `--freecad-appimage PATH` before the subcommand.

`build/gondola.FCStd` is the default generated assembly. The fixture selected by
`config.py` is a regression comparison baseline, not an alternative manufacturing
assembly. Export only manifest-listed print parts. `build/`, logs and temporary
audit files are not committed and may be absent in another environment. Keep retained
evidence and the revision review in Git; do not rely on `/tmp` as the sole record.
The same build also writes `build/gondola_power_options.FCStd` and its separate
optional platform STL/STEP/manifest. This document illustrates one BEC and one SVPDB on
the accessory carrier, with hidden main-assembly context. It is not the default
battery installation. The validator audits these files without regenerating them;
the bundle places them under `optional_power/`. Optional boards, platform and
fasteners must not be added to baseline installed quantities or mass automatically.
GUI entry points are `build_gondola.FCMacro` and `preview_gondola.FCMacro`.
They reload the local `gondola` package and clear its generated bytecode before
running, so repeated GUI invocations use current source. This does not close
existing documents; normal build/preview output replacement still applies.

## Blender derivative

After native validation, `python3 tools/blender_review/run.py --render-stills`
generates `build/blender_review/cad_review.blend`; add `--open` when opening it is
requested. The reviewed setup used Blender 5.2.2. Verify the derivative after tool
or Blender changes, preserving its source/CAD identities and `verification.json`.

The verifier compares evaluated Blender transforms with sampled native poses.
This is prescribed rigid motion, not collision, dynamics, wire, friction or strength
simulation. Optical host transfer and powered alignment are not simulated.
The separate optional-power installation is inspected in native CAD, not included
in this baseline Blender derivative.
The display is rotated as a whole so neutral sensor aim points down; native CAD
coordinates are unchanged. Blender-only edits do not by themselves justify promoting
the CAD regression fixture.
