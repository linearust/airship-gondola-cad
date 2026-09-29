# AI agent guide

Sole operating guide; no separate handoff. Later user instructions override this
file and historical references. Keep user requirements, current choices, catalog
claims, design allowances and measurements distinct. Resolve conflicts explicitly.

Before editing: inspect Git status, preserve others' edits/manual CAD, run
`python3 -m gondola status`, then read the affected contracts and evidence below.
Source defines implementation, not physical qualification or immutable requirements.

## Persistent user intent

- Design for lightweight LTA use. Prefer simple, printable, assemblable structure
  over marginal weight savings; modest mass gain is acceptable, with no fixed target.
- Integrate parts unless assembly, motion or replacement benefits from separation.
- Prefer suitable standard bought parts; minimize custom parts and fastener variety.
- Accommodate fit variation and replacement with simple interfaces, not complexity
  or operating looseness. Favor reusable mounting interfaces where practical.
- Consider assembly, wiring, motion clearance and balance together; use realistic
  manufacturing margins and distinguish verified interfaces from assumptions.
- Prefer simple major layout dimensions in the actual CAD for repeatable testing;
  do not substitute rounded simulation values for feasible design changes.
- Redesign/reselect when the whole assembly improves. Existing geometry and methods
  are means, not goals.

## Current scope, constraints and design

Specific user constraints remain active; current geometry is replaceable within
existing authorization. Do not turn implementation details into permanent rules.

- **Scope:** 2 m indoor LTA gondola, two independent tilt propulsors and battery/
  electronics; fins, fin servos and aft yaw thruster excluded. Consider outdoor GPS.
- **Explicit constraints:** metric hardware; paired servo/input drives detachable
  from the output-bearing frame for replacement; each local/export-axis print
  dimension **≤340 mm**, including coupons. No universal drop-in servo fit is promised.
- **Layout/attachment brief:** propulsion / battery / FC-and-electronics regions;
  FC near neutral motor rear wires, battery opposite, rail positions for CG trim.
  Tape rail to balloon; close hand-pressure slide fit with additional bolt retention.
  Wrap existing members instead of tie-only features; retain useful spare device/stack
  patterns even when unused. Keep optical sensing relocatable and unobstructed downward.

**Manufacturing basis:** Creallo, unfilled PA12; SLS/MJF, grade/finish and one-piece
acceptance pending. Screen both process envelopes; allow wall/fit margin and powder
removal. Qualify fit with coupons matching full-part process, material, finish and
feature orientation.

**BI:** retains actual 150 mm main-axis spacing and 50 mm contact-plane-to-axis
height. The optical head uses an existing universal carrier side slot, eliminating
its separate rail shoe; two foot fasteners and one pitch fastener use ordinary
M2 hardware. Default: battery +X edge, pivot Z35 mm. Output supports balance service
space with 70 mm bearing spacing, 10 mm grips and 6 mm posts; driven/idler/input
rods are 34/20/18 mm. The current 40 mm propeller carrier has a Ø50/46 mm guard.
A separate swept-space check reserves room for a future 50 mm replacement rotor;
the current carrier does not accept that propeller. Central carrier attachment,
OEM-horn adapter and detachable paired-servo architecture remain.
[Current design review](references/bi_design_review.md),
[verification](references/bi_design_verification.json),
[OEM horn evidence](references/servo_horn_compatibility.md),
[horn/service maintenance review](references/horn_service_review_2026-09-29.md).
Evidence covers its recorded source/files only. Selections are not proof of purchase.

| Area | Selection / limits | Read before changing |
| --- | --- | --- |
| FC / battery | MicoAir H743V2 AIO **45A AM32**, existing 2S pack; **2S support confirmed by user, 2026-09-29**. Revision/minimum voltage unspecified; installed power untested. | [FC](references/controller_selection_review.md) |
| Drive | Two X06 V6.0; metric m0.5 **48T input / 16T output**, both Ø3 mm nominal bores. Bounded ±180° target; small shortfall allowed, no wraparound. No alternate ratio/collective mode implemented. | [selection](references/drive_selection_review.md), [gear evidence](references/kailash_gears_selected_evidence.md) |
| Horns | Manufacturer X06 stock plastic half arm 1 on both sides. Preserve supplied STEP geometry except existing Ø1 mm holes at 6.8/13.2 mm enlarged to Ø1.5 mm; rear M1.4×8 screws/front M1.4 nuts. Near Ø1.8 mm round hole and far 1.8 × 2.4 mm slot in the adapter; no washers. Preserve factory axes and OEM centre retention; resin, mass and installed fit remain unmeasured. | [profiles](gondola/contracts/servo_horns.py), [compatibility](references/servo_horn_compatibility.md) |
| Shafts / bearings | Nominal Ø3 mm 304 rod, generic 3×6×2.5 mm bearings; precision replacement rod allowed if fit fails. No established h5 tolerance or NSK/ISC identity. Integral outer-ring capture, separate shaft grip/axial stops. **No purchased spacers**; rejected 3×5×3 bush contacts shields. | [cart adaptation](references/cart_adaptation_review.md), [retention](references/retention_review.md) |
| Navigation | One of P-AS, MG-A01/M10 Ultra, bare MG-F10-A in the same region; not MG-F10-C. | [navigation](references/navigation_module_compatibility.md) |
| Optical | One of MTF-02P/MTF-01P on a common adhesive tray. MTF-02P holes unconfirmed; MTF-01P holes intentionally unused. | [sensors](references/optical_sensor_compatibility.md) |
| Radio | Onboard **LR24-F-Mini only**; LR24-F ground, LR900-A removed. | [radio](references/radio_module_compatibility.md) |
| Optional power | One BEC12S-PRO: 24 V → **8 V** → FC/main power and SVPDB-8S input; SVPDB → **5 V** servos. Alternatively SVPDB from 2S. Neither board is in the battery baseline. | [plans](gondola/contracts/power_options.py), [power](references/power_module_compatibility.md) |

Default: P-AS + LR24-F-Mini + MTF-02P. Alternatives are not simultaneous installations
or purchase instructions. Gear material/masses unresolved; missing mass is unknown.

**Already answered:** metal M2/M3 screws/nuts and GH1.25 kit owned; varied M1.4/M1.6
kit lengths. Heads/engagement still need checking. Gear M3 set-screw length/point/
protrusion unresolved, screw solids unmodeled. Y servo harness, push-on rings, nylon
M2 standoffs and unrelated cart items are outside CAD requirements. [Cart record](references/cart_review_2026_09_27.json).

**Superseded:** carbon-adapter-based rail architecture, 35A Bluejay, DS-M005,
60T/20T, imperial 48DP, MISUMI-only purchasing, two-BEC/exact-5.2-V servo scheme,
and the three-metal-horn universal radial-slot adapter. Its drawings remain historical
references; they are not current compatibility requirements.
Do not restore these from old records. The 59° example was hypothetical.
Changing a saved gear-ratio property does not regenerate or validate the mechanism.

**Antennas:** MG-F10 direct/remote both allowed; prefer remote upward for GPS. Native
+Z is away from balloon, downward. Direct SMA seating unmeasured; remote mount/lead/
location unmodeled. Check reception/orientation/occlusion, including MG-A01 patch.

**Power:** BEC's catalog 8 V / 5 A is shared by main loads and SVPDB input, including
losses—not additive to SVPDB's output rating. An 8 V main rail is nominally consistent
with confirmed 2S FC support; installed loads/transients/cooling remain unverified. Separate-regulator servo positives must be
disconnected from FC 5 V; common ground, never parallel regulator positives.
Battery/tether are alternatives, with no simultaneous-input/switching design.
The illustrated direct-tether layout moves optics to accessory NegativeX; it rejects
the MG-F10 direct helix there. Use its remote-antenna option or another checked layout.
Power-board pads are electrical, not confirmed mounting holes. Verify insulation,
terminal access and tether strain relief/routing clear of propellers and optical view.

## Current design contracts and change checks

The architecture-specific checks below describe BI. Preserve them during refactors;
for intentional redesign, revise affected geometry, native controls/metadata, BOMs,
reservations and checks together rather than freezing the old implementation.
Read `design.release_status()` before readiness claims. Geometry/coupons
are not physical fit, strength, retention/creep/fatigue, adhesive, electrical/thermal,
RF/magnetic, installed mass/CG or flight qualification. Missing evidence stays open.

- Use shared oriented datums and correct movable parents (`wiring_reserves.parent_name()`),
  not merely matching world positions. Legacy object IDs can name old devices; read profiles.
- Rail clamps must bear on complete head lands, not flex gaps. Tape proximity is
  reported from saved geometry, not a load qualification or CG-trim restriction.
  Qualify the close shoe fit straight and at actual installed curvature; no minimum
  bend radius is established. Preserve underside screw-head and service access.
- Three identical `UniversalEquipmentCarrier` prints: plate/openings have 90° rotation
  and X/Y reflection symmetry; shoe/clamp are directional. Preserve FC annuli, P-AS
  slot seats/datum offset and continuous lands/tape patches. M2 heads are unqualified
  for M3-width slots. Mini body/tape/connector datums jointly clear both rail-clamp and
  power-foot service paths. Bench-service off rail; tape wings are not equipment pads.
- The central M2 hole has a side-loaded ordinary nut and blind floor above the
  rail. Load the nut off rail; select screw length from the actual stack. A bare
  plate's nominal M2×5 example leaves 0.4 mm floor clearance. Check the received
  nut in this vertical printed seat; the rail coupon has a different orientation.
  Do not bottom the screw or
  assume the floor is a torque stop. This optional joint is excluded from baseline
  hardware. Preserve continuous adhesive strips around the central opening.
- Optical is a child of its carrier: `CarrierHostName` records the parent and
  `MountSide` selects its existing ±X edge slots; there is no separate rail control.
  `optical_interface.attach_to_host` changes host; `optical_mount.set_pitch` controls
  manual pitch-Y only. Default battery +X clears both sensors. Shared slot geometry
  does not qualify every populated host/edge or power stack: follow composed checks,
  including rejected configurations. Recheck view, connector and service clearances
  after relocation. No roll correction, self-levelling or physical pointing
  qualification is claimed.
- Check the selected manufacturer horn against its retained STEP, the two prepared
  horn holes, round/slot interface, seating/concentricity, screw/nut direction/access,
  servo clearance and ordered removal. Remove the paired module first; on the
  bench, release only the rear ear nuts for individual servo removal. Retain
  both M1.6 ear bolts in the moving servo unit.
  Fit those bolts before the adapter; withdraw them only after adapter removal. Nominal geometry is not physical measurement.
  X06 radial-load capacity, loaded travel/torque retention remain unverified;
  slots do not cure running eccentricity. Check received hardware,
  FC damping/insulation and bearing shields; never restore the rejected shield-contact bush.
- Check neutral/coupled rotation, axial travel and complete service paths, not endpoints.
  Separate intended contacts from collisions; distinguish sampled checks from continuous
  bounds. Motor leads rotate, servo-case leads do not. Reserves are not harness lengths
  or flexible-wire proof; verify installed bends, tension, rubbing and twist.

## Source map

Read affected source/references before edits; detailed dimensions/BOMs stay there.
References may describe older revisions; do not rewrite historical audit records.
Keep required evidence in Git—`build/`, `/tmp`, Downloads and prior chats may be absent.

| Responsibility | Source |
| --- | --- |
| Decisions, manufacture, inventory, unresolved issues | [contracts/design.py](gondola/contracts/design.py) |
| Device interfaces/options; drive/hardware/fasteners; horns/power | [contracts/](gondola/contracts/) |
| Plate/fixed bores/heights; slots; carrier/device/tape datums | [parts/](gondola/parts/): `mounting_plate.py`, `mounting_slots.py`, `equipment_mounts.py` |
| Equipment bodies/placement/wires; optical; power supports | [parts/](gondola/parts/): `equipment_envelopes.py`, `equipment_layout.py`, `wiring_reserves.py`; `optical_interface.py`, `optical_mount.py`; `stack_interface.py`, `power_mount.py` |
| Hierarchy/geometry; prints/purchases/mass; provenance/CLI | [gondola/](gondola/): `assembly.py`, `cad.py`; `print_export.py`, `procurement.py`, `mass_budget.py`; `config.py`, `provenance.py`, `bundle.py`, `cli.py`, `freecad_runtime.py` |
| Checks | [validation/](gondola/validation/), [tests/](tests/) |

Interface rationale: [layout/wiring](references/layout_and_wiring_review.md),
[rail joint](references/rail_joint_review.md), [rail fit](references/rail_fit_review.md).

## Verification / artifacts

**Docs only:** check meaning, source consistency, links and `git diff --check`; no CAD
regeneration/test rerun for prose. Design-input/code corrections need relevant checks.

**Source changes:** Python 3.11+; run Ruff check/format check using `uvx ruff==0.16.8`
on `gondola tests build_gondola.FCMacro preview_gondola.FCMacro`. Offline unittest
skips FreeCAD cases. Before accepting changed CAD, run native tests with **no skips**:

```sh
python3 - <<'PY_NATIVE'
import os, subprocess
from gondola.config import REPO_ROOT
from gondola.freecad_runtime import locate_appimage, mounted_appimage
with mounted_appimage(locate_appimage()) as mount:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT), str(mount / "usr/lib")))
    for folder in ("tests", "tools/blender_review", "tools/simulation"):
        subprocess.run([str(mount / "AppRun"), "python", "-m", "unittest",
                        "discover", "-s", folder, "-v"],
                       cwd=REPO_ROOT, env=env, check=True)
PY_NATIVE
```

Reviewed: FreeCAD 1.1.3, Blender 5.2.2. The launcher finds FreeCAD AppImages in
`~/Applications`/`~/Downloads` or via `FREECAD_APPIMAGE`. Recheck kernel differences
on upgrades.

Preserve `config.py`'s pinned fixture during behavior-preserving refactors. Intentional
shape/native-contract changes require independent old/new shape, placement, control
and metadata review before re-pinning; never replace a fixture to hide failure.
Freeze source, then run in order, stopping on failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola compare
python3 -m gondola validate
python3 -m gondola bundle
```

Build/preview overwrite outputs; preserve manual edits first. Preview needs a display
and saves the previewed CAD files, so it precedes file-bound checks. Inspect assembly, print
layout and the optical-carrier view; preserve the configured rail station before saving. Alternate
paths: put `--output-dir PATH` / `--freecad-appimage PATH` before the subcommand;
use the output directory consistently. Retain exact-source/file verification in Git.
Fingerprint covers `gondola/**/*.py`, files in `gondola/data/` and root `.FCMacro`,
excluding docs/tests/reference evidence/Blender tools: a matching fingerprint alone
does not establish their freshness. Retain the manufacturer STEP and its source
archive/provenance together; nominal CAD is not a delivered-part measurement.

Untracked `build/gondola.FCStd` is the generated assembly, **not the fixture**.
Export only manifest-listed prints. `build/gondola_power_options.FCStd` is a separate
optional installation with copied main context, audited and bundled under
`optional_power/`; do not add its boards/platform/fasteners to baseline mass/BOM.
GUI macros `build_gondola.FCMacro` / `preview_gondola.FCMacro` reload local code but
leave existing documents open.

After native validation, `python3 tools/blender_review/run.py --render-stills`
creates `build/blender_review/cad_review.blend`; add `--open` when requested.
Verify source/CAD hashes and `verification.json`. This checks sampled prescribed
rigid motion, not continuous collisions, dynamics, wires or strength. No optical
carrier transfer/powered alignment; optional power is reviewed in FreeCAD. Display uses
a whole-scene X half-turn without changing native coordinates. Blender-only changes
do not justify re-pinning CAD.

Simulation: [parameter sheet](references/simulation_parameters.md) and its linked
SI snapshot separate exact CAD datums and unmeasured whole-airship inputs.
`python3 tools/simulation/export_parameters.py` reads validated saved CAD without
modifying it. Re-export after layout changes; native coordinates are not automatically
CV/FRD coordinates. Exporter-only changes need its native tests and a fresh extraction,
not a CAD re-pin; do not infer physical mass/CG from equipment-envelope volumes.

## Collaboration

Report results, rationale, checks and material uncertainty concisely in Korean.
Proceed within authorization; do not re-ask answered questions. Old timed question
windows were session-specific. Push reviewed changes as previously requested,
subject to later instructions; verify remote state before claiming success.
Show current, provenance-checked CAD when asked. Keep this guide AI-only; provide
human purchase/inspection/assembly deliverables separately when requested.

The [Notion plan](https://app.notion.com/p/3e3ee52b5792806c94acc1f798594bad) is auxiliary:
improve either side on merit. Discuss and agree page changes before editing; honor
existing agreement. Never claim synchronization without checking the live content.
