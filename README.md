# AI agent guide

Sole operating guide; no separate handoff. Later user instructions override this
file and historical references. Keep user requirements, current choices, catalog
claims, design allowances and measurements distinct. Resolve conflicts explicitly.

Before editing: inspect Git status, preserve others' edits/manual CAD, run
`python3 -m gondola status`, then read the affected contracts and evidence below.
Source defines implementation, not physical qualification or immutable requirements.

## User requirements

- **Scope:** 2 m indoor LTA gondola: two independently tilting main propulsors,
  battery/electronics. Fins, fin servos and aft yaw thruster excluded. Consider outdoor GPS.
- **Priority:** simple integrated, printable/assemblable structure before weight
  optimization; no fixed mass target, modest gain acceptable. Avoid needless bends,
  holes, thin branches, caps and fasteners. Preserve support roots/servo reaction
  paths without excessive LTA stiffness. Redesign/reselect parts when overall better.
- **Separation exception:** paired servos/input drives must detach from propulsion/
  output-bearing frame for replacement; not universal drop-in servo compatibility.
- **Metric, bought parts:** buy suitable standard parts rather than print them without
  clear benefit. Minimize screw/nut types and unnecessary washers. Use low-load latches/slides when retention/alignment/
  service remain sound. Confirmed device holes or existing tape/Velcro surfaces suffice;
  no invented precision interfaces from photos. Availability is not quality evidence.
- **Simple flexibility:** open geometry, slots or local preparation; module replacement
  can beat complex adjustment. Align then clamp, never run loose. Preserve shaft axes,
  torque transfer and bearing support; gear face/hub thickness may be critical.
- **Common carriers:** identical square battery/FC/navigation plates; symmetric, mostly
  straight/curved slots covering confirmed device axes and useful spare patterns.
  Preserve lands/tape areas. No F-Mini-only plate/asymmetric utility tab. Spare holes
  do not prove arbitrary hardware or simultaneous-stack compatibility.
- **No tie-only holes/slots/tabs:** wrap existing members. Requested spare device/stack
  patterns are different; retain useful ones even when currently unused.
- **Layout:** propulsion / battery / FC-and-electronics regions. FC near neutral motors'
  rear wires, battery opposite; rail positions trim CG. Provide FC underside wiring,
  connector/tool access and restrained rotating-wire loops without excessive space.
- **Optical:** compact, relocatable, unobstructed downward view. One lockable pitch axis
  suffices for longitudinal curvature with a lower-centreline rail; not self-levelling.
- **Rail:** tape to balloon; deliberate hand-pressure sliding with little rocking,
  bolts for additional retention; qualify fit with coupons.
- **Manufacture:** Creallo; each local/export-axis dimension **≤340 mm**, including
  coupons; screen exports against both published SLS/MJF envelopes while undecided.
  Unfilled PA12; process/grade/finish and one-piece acceptance pending. Allow wall/fit
  margin above supplier minima and powder removal. Match coupon/full-part process, material, finish and feature orientation.

## Current design, not permanent constraints

**BB:** square slotted carriers, compact single-pitch optical pedestal.
[Design](references/square_mount_review.md) ·
[original verification](references/square_mount_verification.json) ·
[refactor verification](references/bb_refactor_verification.json).
Evidence covers its recorded source/files only. Selections are not proof of purchase.

| Area | Selection / limits | Read before changing |
| --- | --- | --- |
| FC / battery | MicoAir H743V2 AIO **45A AM32**, existing 2S pack. Official input-range conflict leaves 2S and 8 V suitability unresolved; confirm supplied revision. | [FC](references/controller_selection_review.md) |
| Drive | Two X06 V6.0; metric m0.5 **48T input / 16T output**, both Ø3 mm nominal bores. Bounded ±180° target; small shortfall allowed, no wraparound. No alternate ratio/collective mode implemented. | [selection](references/drive_selection_review.md), [gear evidence](references/kailash_gears_selected_evidence.md) |
| Horns | All three retained 4 mm/15T drawings share an open radial-slot adapter; sides may differ. X06 spline compatibility is user-accepted, not measured. Two metal profiles have M1.6 threads; KST 0415.13 needs specified preparation/fasteners. Preserve factory axes and OEM centre retention. | [profiles](gondola/contracts/servo_horns.py), [compatibility](references/servo_horn_compatibility.md) |
| Shafts / bearings | Nominal Ø3 mm 304 rod, generic 3×6×2.5 mm bearings; precision replacement rod allowed if fit fails. No established h5 tolerance or NSK/ISC identity. Integral outer-ring capture, separate shaft grip/axial stops. **No purchased spacers**; rejected 3×5×3 bush contacts shields. | [cart adaptation](references/cart_adaptation_review.md), [retention](references/retention_review.md) |
| Navigation | One of P-AS, MG-A01/M10 Ultra, bare MG-F10-A in the same region; not MG-F10-C. | [navigation](references/navigation_module_compatibility.md) |
| Optical | One of MTF-02P/MTF-01P on a common adhesive tray. MTF-02P holes unconfirmed; MTF-01P holes intentionally unused. | [sensors](references/optical_sensor_compatibility.md) |
| Radio | Onboard **LR24-F-Mini only**; LR24-F ground, LR900-A removed. | [radio](references/radio_module_compatibility.md) |
| Optional power | One BEC12S-PRO: 24 V → **8 V** → FC/main power and SVPDB-8S input; SVPDB → **5 V** servos. Alternatively SVPDB from 2S. Neither board is in the battery baseline. | [plans](gondola/contracts/power_options.py), [power](references/power_module_compatibility.md) |

Default: P-AS + LR24-F-Mini + MTF-02P. Alternatives are not simultaneous installations
or purchase instructions. Gear material/masses unresolved; missing mass is unknown.

**Already answered:** metal M2 screws/nuts and GH1.25 kit owned; varied M1.4/M1.6
kit lengths. Heads/engagement still need checking. Gear M3 set-screw length/point/
protrusion unresolved, screw solids unmodeled. Y servo harness, push-on rings, nylon
M2 standoffs and unrelated cart items are outside CAD requirements. [Cart record](references/cart_review_2026_09_27.json).

**Superseded:** carbon-adapter-based rail architecture, 35A Bluejay, DS-M005,
60T/20T, imperial 48DP, MISUMI-only purchasing, two-BEC/exact-5.2-V servo scheme.
Do not restore these from old records. The 59° example was hypothetical.
Changing a saved gear-ratio property does not regenerate or validate the mechanism.

**Antennas:** MG-F10 direct/remote both allowed; prefer remote upward for GPS. Native
+Z is away from balloon, downward. Direct SMA seating unmeasured; remote mount/lead/
location unmodeled. Check reception/orientation/occlusion, including MG-A01 patch.

**Power:** BEC's catalog 8 V / 5 A is shared by main loads and SVPDB input, including
losses—not additive to SVPDB's output rating. Installed loads/transients/cooling and
FC input compatibility are unverified. Separate-regulator servo positives must be
disconnected from FC 5 V; common ground, never parallel regulator positives.
Battery/tether are alternatives, with no simultaneous-input/switching design.
Power-board pads are electrical, not confirmed mounting holes. Verify insulation,
terminal access and tether strain relief/routing clear of propellers and optical view.

## Change boundaries

Update affected geometry, native controls/metadata, BOMs, reservations and checks
together. Read `design.release_status()` before readiness claims. Geometry/coupons
are not physical fit, strength, retention/creep/fatigue, adhesive, electrical/thermal,
RF/magnetic, installed mass/CG or flight qualification. Missing evidence stays open.

- Use shared oriented datums and correct movable parents (`wiring_reserves.parent_name()`),
  not merely matching world positions. Legacy object IDs can name old devices; read profiles.
- Three identical `UniversalEquipmentCarrier` prints: plate/openings have 90° rotation
  and X/Y reflection symmetry; shoe/clamp are directional. Preserve FC annuli, P-AS
  slot seats/datum offset and continuous lands/tape patches. M2 heads are unqualified
  for M3-width slots. Mini body/tape/connector datums jointly clear both rail-clamp and
  power-foot service paths. Bench-service off rail; tape wings are not equipment pads.
- Optical/power feet share outer slots, not datums/supports. Bound full translation/yaw,
  not circular-hole float; openings must pass through fused supports. No optical+power
  on one host or unlimited stacking. Optional inventory remains separate.
- Optical uses `optical_interface.attach_to_host()` / `optical_mount.set_pitch()`:
  pitch-Y only, bonded uninterrupted tray, clamped foot/pivot. Without optional power,
  P-AS/MG-A01 allow battery/FC hosts; direct MG-F10-A allows battery only due to FC-host
  view obstruction. Power can further restrict hosts: follow its report. Navigation/
  propulsion hosts and arbitrary corners are unqualified. Retain rejected cases;
  the saved selected configuration must pass.
- Check all horn profiles, seating/concentricity, screw/nut direction/access, servo
  clearance and ordered removal. X06 radial-load capacity, loaded travel/torque retention
  remain unverified; slots do not cure running eccentricity. Check received hardware,
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
    for folder in ("tests", "tools/blender_review"):
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
and saves both CAD files, so it precedes file-bound checks. Inspect assembly, print
layout and both optical-host views; restore configured host before saving. Alternate
paths: put `--output-dir PATH` / `--freecad-appimage PATH` before the subcommand;
use the output directory consistently. Retain exact-source/file verification in Git.
Fingerprint covers `gondola/**/*.py` and root `.FCMacro`, excluding docs/tests/evidence/
Blender tools: a matching fingerprint alone does not establish their freshness.

Untracked `build/gondola.FCStd` is the generated assembly, **not the fixture**.
Export only manifest-listed prints. `build/gondola_power_options.FCStd` is a separate
optional installation with hidden main context, audited and bundled under
`optional_power/`; do not add its boards/platform/fasteners to baseline mass/BOM.
GUI macros `build_gondola.FCMacro` / `preview_gondola.FCMacro` reload local code but
leave existing documents open.

After native validation, `python3 tools/blender_review/run.py --render-stills`
creates `build/blender_review/cad_review.blend`; add `--open` when requested.
Verify source/CAD hashes and `verification.json`. This checks sampled prescribed
rigid motion, not continuous collisions, dynamics, wires or strength. No optical
host transfer/powered alignment; optional power is reviewed in FreeCAD. Display uses
a whole-scene X half-turn without changing native coordinates. Blender-only changes
do not justify re-pinning CAD.

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
