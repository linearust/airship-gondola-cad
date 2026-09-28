# AI agent instructions

This is the sole agent operating guide: it records user requirements, design
priorities, current implementation boundaries and verification workflow. Do not
create a separate handoff document. Human-facing purchase lists, inspection aids
and assembly explanations are separate deliverables when requested.

## Authority and starting state

1. Read the latest user instructions and inspect Git status. Preserve unrelated
   edits and meaningful manually changed CAD before regenerating output.
2. Run `python3 -m gondola status`. Read the relevant source contracts and retained
   evidence before editing. Source defines the implemented design, not physical
   qualification or an immutable user requirement.
3. Later user decisions override this guide and older references. Distinguish
   user requirements, current engineering choices, catalog claims, allowances and
   measurements. Resolve contradictions explicitly; do not silently convert one
   category into another.

Current implemented baseline: **BB**, square printed carriers with a symmetric
hole/slot array and a compact single-axis optical pedestal. See the
[design review](references/square_mount_review.md),
[original BB verification](references/square_mount_verification.json), and
[geometry-preserving refactor verification](references/bb_refactor_verification.json).
Those records apply to their recorded source and files; later changes need their
own relevant checks. Historical fixtures/reports are evidence, not active build
instructions. Bought-carbon-plate rail architectures were tried and rejected;
do not restore them from an old attachment or commit.

## Persistent user requirements and design priorities

- **Scope:** gondola for a 2 m-class indoor LTA blimp: two main propulsors and their
  independent tilt mechanism, battery and electronics support. Fins, fin servos
  and the aft yaw thruster are outside this CAD. Outdoor GPS reception is also a
  requested consideration, not a claim of outdoor flight qualification.
- **Simple integrated structure first:** combine parts without a functional reason
  for separation, ensure printing and assembly are practical, then optimize weight.
  There is no fixed mass target. A modest mass increase is acceptable for simpler,
  stronger or less error-prone geometry. Avoid purposeless bends, lightening holes,
  thin branches, caps and fasteners. Match stiffness to LTA loads while preserving
  sound support roots and servo reaction paths.
- **Deliberate exception:** keep the paired-servo/input-drive module removable from
  the propulsion/output-bearing frame for future servo replacement. Do not merge
  these modules. This does not promise drop-in compatibility with every servo.
- **Metric and purchased parts:** use metric gear/mechanical specifications, readily
  available parts where suitable, and fewer fastener types. Prefer one ordinary
  nut type per size where feasible; omit unnecessary washers. Do not print a readily
  bought part without a clear system benefit. AliExpress availability does not
  establish a standard, precision tolerance or verified material.
- **Simple tolerance accommodation:** favor open geometry, assembly clearance,
  straightforward slots and documented local preparation over elaborate adjusters.
  Module replacement may be better than adjustment. Slots are aligned and clamped
  before operation, never deliberately loose in service. Preserve functional shaft
  axes, torque transfer, bearing support and retention; gear face/hub thickness can
  affect all of these and is not automatically a noncritical dimension.
- **Best overall design:** existing geometry and purchased-part selections are not
  permanent constraints. Consider major redesign or shaft/bearing/gear reselection
  when the complete coupling, retention, weight, sourcing and service trade-off
  improves. Do not preserve a weaker solution merely to avoid redesign.
- **Fastening:** use latches/slides instead of bolts where they simplify low-load
  joints without sacrificing alignment, retention or serviceability. Use confirmed
  device mounting holes when useful; the early blanket ban on holes was withdrawn.
  Tape, Velcro or wrapped ties are sufficient for suitable devices; avoid dedicated
  brackets when existing surfaces suffice. Never invent holes, spline dimensions,
  thread depths or connector datums from photographs.
- **Common plates:** favor identical square battery/FC/navigation carriers and a
  symmetric breadboard-like array, mostly straight/curved slots, that includes the
  selected devices' confirmed axes. Retain useful spare module patterns even if
  currently unused. Preserve load-bearing lands and adhesive areas; extra openings
  are not free of structural or compatibility costs. No dedicated F-Mini plate,
  long extension or asymmetric utility tab is wanted.
- **No dedicated tie features:** do not add cable-tie-only holes, slots or tabs.
  Velcro and ties wrap existing members. Requested spare device/stack holes are a
  different feature. A common pattern does not certify arbitrary hardware,
  simultaneous payloads or every stack combination.
- **Three mass regions:** propulsion; battery or optional tether-power hardware;
  FC and other electronics. Place the FC near neutral motors' rear wire exits and
  the battery on the opposite side. Allow rail-position trim; symmetry alone does
  not establish CG. Provide FC underside wiring space, connector mating/removal
  and tool access, and restrained loops for rotating motor leads without excessive
  unused clearance.
- **Optical placement:** allow relocation to suitable common carrier/stack positions,
  with an unobstructed downward view. One lockable pitch axis is acceptable because
  the rail is planned on the balloon's lower centreline and only longitudinal
  curvature needs correction. Added mass or height does not make it self-levelling.
- **Rail fit:** rail-to-balloon attachment uses tape. Rail shoes should slide with
  deliberate hand pressure and little rocking; bolts add position retention.
  Qualify actual printed fit with coupons, rather than claiming raw print tolerance
  guarantees a press-fit feel or retention force.
- **Manufacture:** Creallo is the reference supplier; maximum nominal printed-part
  dimension is **340 mm**. Unfilled PA12 with SLS or MJF is the current basis;
  final process, grade and finishing remain open. Use reasonable functional wall
  and fit margins above supplier minima. Check rotated build envelopes, functional
  sections and powder removal; a size table is not one-piece order acceptance.

## Current selections and unresolved interfaces

These are implemented choices, not permanent design rules or proof of purchase.
Detailed dimensions, quantities and preparation lengths belong in source contracts
and generated BOMs. Change selections and all affected geometry, native metadata,
BOMs, reservations and verification together.

| Area | Current choice and boundary | Authority/evidence |
| --- | --- | --- |
| FC and battery | MicoAir H743V2 AIO **45A AM32**, existing 2S pack. Official input-range evidence conflicts; verify the supplied revision before accepting 2S or an 8 V tether rail. Do not silently substitute the older 35A Bluejay board or a higher-voltage pack. | [FC contract](gondola/contracts/equipment_interfaces.py), [review](references/controller_selection_review.md) |
| Drive | Two KST X06 V6.0 servos, module 0.5 **48T input / 16T output**, both nominal Ø3 mm bores. Bounded nominal ±180° target, small travel shortfall allowed; no continuous wraparound. Alternate ratios/collective drive are not implemented. | [drive contract](gondola/contracts/drive.py), [selection](references/drive_selection_review.md), [seller evidence](references/kailash_gears_selected_evidence.md) |
| Horns | One open radial-slot adapter supports all three retained 4 mm/15T drawings, including mixed left/right choices. Preserve the user-accepted X06 spline-compatibility premise, factory axes and OEM centre retention. Two metal horns have M1.6 threads; KST 0415.13 requires its documented preparation/fasteners. | [per-side profiles](gondola/contracts/servo_horns.py), [compatibility](references/servo_horn_compatibility.md) |
| Shafts and bearings | Nominal Ø3 mm 304 rod and generic 3×6×2.5 mm bearings. A precision replacement rod is allowed if received fit is unsuitable. Neither h5 tolerance nor NSK/ISC identity is established. | [cart adaptation](references/cart_adaptation_review.md), [retention](references/retention_review.md) |
| Bearing retention | Integral outer-ring capture and separate shaft grip/axial stops; **no purchased spacers**. Rejected 3×5×3 bush contacts shields. Actual latch retention, release and creep remain unqualified. | [retention review](references/retention_review.md) |
| Navigation | **One of** P-AS, MG-A01/M10 Ultra, or bare MG-F10-A replaces the others on the same region. MG-F10-C case version is outside scope. | [profiles](gondola/contracts/equipment_options.py), [navigation review](references/navigation_module_compatibility.md) |
| Optical | **One of** MTF-02P or MTF-01P on the same adhesive tray. No confirmed MTF-02P mounting pattern; MTF-01P holes are deliberately unused. | [profiles](gondola/contracts/optical_sensors.py), [sensor review](references/optical_sensor_compatibility.md) |
| Radio | Onboard **LR24-F-Mini only**; full LR24-F stays on the ground. LR900-A support was removed. | [radio review](references/radio_module_compatibility.md) |
| Optional power | One BEC12S-PRO: 24 V tether → **8 V** → FC/main power and SVPDB-8S input; SVPDB → **5 V** servos. Alternatively one SVPDB on the 2S battery. Base battery assembly includes neither optional board. | [plans](gondola/contracts/power_options.py), [power review](references/power_module_compatibility.md) |

Default equipment is P-AS + LR24-F-Mini + MTF-02P. Alternatives are not simultaneous
installation or purchase instructions. Published/selected mass is not measured
installed mass; missing values are unknown, not zero. Gear material-description
conflicts and measured masses were deferred by the user, not resolved.

The user already has metal M2 screws/nuts and a GH1.25 kit, and reported varied
lengths in the M1.4/M1.6 screw kit. Do not ask again; actual head envelopes and
usable engagement still need checking. Gear M3 set-screw length, point and protrusion
are unresolved and actual screw solids remain unmodeled. Servo Y harnesses,
push-on ring kits, nylon M2 standoff kits and unrelated cart items are not CAD
installation requirements. See the [retained cart review](references/cart_review_2026_09_27.json).

Earlier DS-M005, 60T/20T, imperial 48DP and MISUMI-only purchase choices are
superseded. The user's 59° servo example was hypothetical, not a measurement.
A ratio property edit does not regenerate gear teeth or validate a new drive.

MG-F10 antenna **direct and remote attachment are both allowed**; the earlier
mandatory-direct instruction was superseded. Prefer remote upward placement when
GPS reception matters. Native +Z points away from the balloon, downward. Direct
SMA location/seating is not measured; the CAD reservation does not prove reception.
Remote mount, lead and location are unmodeled. MG-A01 patch orientation and balloon
occlusion also require installed verification.

For optional power, the BEC's 8 V / 5 A catalog limit is shared by main loads and
SVPDB input, including conversion losses; installed current, transients and thermal
margin are unverified. Disconnect servo positives from FC 5 V when using a separate
regulator, keep common ground, and never parallel regulator positives. Battery and
tether are alternative inputs; no simultaneous connection or automatic switch is
designed. Neither power board has a confirmed mechanical hole pattern: electrical
pads are not mounting holes. Insulating contact, cooling, terminal access, tether
strain relief/routing and propeller clearance require installed checks.

## Mechanical and verification boundaries

- Maintain shared oriented datums and transform local directions into assembly
  coordinates. Keep geometry, native controls, BOM and clearance ownership aligned.
  `wiring_reserves.parent_name()` defines a reservation's movable owner; coincident
  world coordinates cannot replace correct parenting. Older device names remain
  in some native IDs: inspect selected profile properties/labels, not IDs alone.
- The three `UniversalEquipmentCarrier` prints share their complete plate pattern.
  The plate is symmetric under 90° rotation and X/Y reflection; the integral rail
  shoe/clamp is directional. Preserve continuous lands, fixed FC annuli, P-AS slot
  seats and declared adhesive patches. The small P-AS datum offset maps its real
  axes onto common slots. Existing M2 heads are not qualified for M3-width slots;
  spare openings do not imply selected fastener stacks or extra baseline washers.
- The Mini uses the navigation carrier's rail-facing side, with separate body/tape
  datums and connector orientation chosen to clear both rail-clamp approaches and
  optional-power foot service. Preserve these together. Tape area does not prove
  retention; balloon curvature, plugged height and actual underside contact remain
  unverified. Detach the carrier for bench access; rail tape wings are not qualified
  electronics mounting faces.
- Optical base and optional power platform share outer host slots but have distinct
  foot datums, registration bounds and supports. Check full slot translation/yaw,
  seating and through-openings after support fusion; do not model the host as two
  locating bores. The power deck shares the plate template, not the entire carrier.
  Do not put optical and power supports on one host simultaneously or infer unlimited
  stacking. Keep optional print/hardware quantities separate from the baseline.
- Use `optical_interface.attach_to_host()` and `optical_mount.set_pitch()` for the
  single Y-axis optical adjustment; no roll stage. The sensor is bonded to its tray;
  foot and pivot are clamped. Preserve its uninterrupted adhesive pad rather than
  forcing spare holes or aperture-obscuring straps onto this small part. Battery
  and FC carriers are checked hosts; navigation/propulsion or arbitrary corners are
  not qualified hosts. Without optional power, P-AS/MG-A01 allow either host, while
  direct MG-F10-A permits battery only because its reservation intersects FC-host
  optical view. Optional power can impose further restrictions: use its report's
  permitted combinations. Retain rejected cases; the saved selected case must pass.
- Check all horn profiles, seating/concentricity, fastener direction and access,
  servo-case clearance and actual ordered module removal. Slots accommodate assembly
  registration, not running eccentricity. X06 external radial-load capacity, loaded
  travel and horn torque retention remain unverified.
- Check neutral, coupled rotation, axial travel and removal paths, not just separated
  endpoints. Distinguish intentional gear/bearing/stop contacts from interference.
  Label sampled checks as sampled and analytical bounds by their scope. Motor leads
  rotate; servo-case leads do not. Cable reserves are not harness cut lengths or
  flexible-wire sweep proof; verify actual bends, strain relief, rubbing and twist.
- Rail/bearing coupons screen fit and retention. Nominal dimensions and prescribed
  latch motion do not prove insertion force, elastic recovery, shield clearance,
  creep or fatigue. Do not reintroduce the rejected shield-contact bush as a shortcut.
  FC underside wiring, damping/insulation and received fastener fit remain open.
- Read `design.release_status()` before reporting readiness. Geometry tests do not
  qualify strength, friction, adhesive, magnetic/RF behavior, installed electrical
  loads, mass/CG or flight. Preserve unresolved interfaces instead of closing them
  through assumptions; a whole-assembly audit covers modeled parts and stated bounds.

## Source ownership

| Concern | Primary files |
| --- | --- |
| Scope, revision, layout, manufacture, inventory and unresolved interfaces | [design.py](gondola/contracts/design.py) |
| Device interfaces and selectable equipment | [equipment_interfaces.py](gondola/contracts/equipment_interfaces.py), [equipment_options.py](gondola/contracts/equipment_options.py), [optical_sensors.py](gondola/contracts/optical_sensors.py) |
| Gears, bought hardware, fasteners, horns and power plans | [drive.py](gondola/contracts/drive.py), [hardware.py](gondola/contracts/hardware.py), [fasteners.py](gondola/contracts/fasteners.py), [servo_horns.py](gondola/contracts/servo_horns.py), [power_options.py](gondola/contracts/power_options.py) |
| Shared plate outline/fixed bores/heights; slot array; carrier support/device/tape datums | [mounting_plate.py](gondola/parts/mounting_plate.py), [mounting_slots.py](gondola/parts/mounting_slots.py), [equipment_mounts.py](gondola/parts/equipment_mounts.py) |
| Equipment placement, bodies and connector reservations | [equipment_layout.py](gondola/parts/equipment_layout.py), [equipment_envelopes.py](gondola/parts/equipment_envelopes.py), [wiring_reserves.py](gondola/parts/wiring_reserves.py) |
| Optical attachment/pitch; optional power portal/platform | [optical_interface.py](gondola/parts/optical_interface.py), [optical_mount.py](gondola/parts/optical_mount.py), [stack_interface.py](gondola/parts/stack_interface.py), [power_mount.py](gondola/parts/power_mount.py) |
| Assembly, native hierarchy and geometry helpers | [assembly.py](gondola/assembly.py), [cad.py](gondola/cad.py), [parts/](gondola/parts/) |
| Print files, purchases and mass estimates | [print_export.py](gondola/print_export.py), [procurement.py](gondola/procurement.py), [mass_budget.py](gondola/mass_budget.py) |
| Checks, fixture, provenance and packaging | [validation/](gondola/validation/), [tests/](tests/), [config.py](gondola/config.py), [provenance.py](gondola/provenance.py), [bundle.py](gondola/bundle.py) |
| Commands and FreeCAD runtime | [cli.py](gondola/cli.py), [freecad_runtime.py](gondola/freecad_runtime.py) |

Consult [layout/wiring](references/layout_and_wiring_review.md),
[rail joint](references/rail_joint_review.md), [rail fit](references/rail_fit_review.md)
and [shape rationale](references/shape_simplification_review.md) when those interfaces
change. References retain revision-specific history; compare them with current
contracts. Do not copy full dimension/BOM tables into this guide. Another environment
may lack `build/`, `/tmp`, Downloads attachments and earlier conversations; preserve
required evidence in Git, while retaining historical audit files without rewriting
what they originally verified.

## Verification and generated artifacts

For documentation-only refactoring, check requirements coverage, factual consistency,
local links and `git diff --check`; do not regenerate CAD or rerun geometry tests
merely for prose changes. A discovered design-input or implementation error needs
its own relevant validation.

For source changes, use Python 3.11+ from the repository root:

```sh
uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
uvx ruff==0.16.8 format --check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
python3 -m compileall -q gondola
python3 -m unittest discover -s tests -v
```

Offline tests skip FreeCAD cases. Before accepting changed CAD artifacts, run native
tests and confirm no skips. The reviewed FreeCAD runtime is 1.1.3; investigate kernel
differences on version changes. The runtime locates an AppImage in `~/Applications`
or `~/Downloads`; `FREECAD_APPIMAGE` overrides it. Preview needs a graphical display.
A reproducible native suite, including Blender export tests:

```sh
python3 - <<'PY_NATIVE'
import os
import subprocess
from gondola.config import REPO_ROOT
from gondola.freecad_runtime import locate_appimage, mounted_appimage

with mounted_appimage(locate_appimage()) as mount:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(REPO_ROOT), str(mount / "usr/lib")))
    for directory in ("tests", "tools/blender_review"):
        subprocess.run(
            [str(mount / "AppRun"), "python", "-m", "unittest", "discover",
             "-s", directory, "-v"],
            cwd=REPO_ROOT, env=env, check=True,
        )
PY_NATIVE
```

Keep the pinned fixture unchanged during behavior-preserving refactoring. Intentional
shape/native-contract changes need an independent old/new geometry, placement, control
and metadata review before updating `config.py`'s fixture/checksum. Never re-pin merely
to hide a failure. The fixture is a regression reference, not a manufacturing assembly.

Freeze source, then run sequentially and stop on failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola compare
python3 -m gondola validate
python3 -m gondola bundle
```

Build and preview overwrite generated files. Preview saves display properties in both
native documents, so it must precede file-bound comparison/validation. Inspect assembly,
print layout and both optical-host views; restore the configured host before saving.
For another directory, pass `--output-dir PATH` before every subcommand; the CLI also
accepts `--freecad-appimage PATH`. Keep relevant checks and exact file/source identities
in revision evidence, not only temporary logs. The source fingerprint includes
`gondola/**/*.py` and root `.FCMacro` files; it excludes tests, docs, evidence and Blender
tools. Matching fingerprints alone do not prove those supporting materials are current.

`build/gondola.FCStd` is the generated baseline assembly. Export only manifest-listed
print parts. `build/gondola_power_options.FCStd` and separate optional STL/STEP/manifest
illustrate one BEC and one SVPDB on the accessory carrier with hidden assembly context;
the validator inspects these files and the bundle includes them under `optional_power/`.
They do not add optional boards/prints/fasteners to baseline installed mass or quantities.
`build/` is untracked and may not exist on another machine.

GUI entry points are `build_gondola.FCMacro` and `preview_gondola.FCMacro`. They reload
the local package and clear its bytecode so repeated GUI runs use current code, but
do not close existing documents. Preserve meaningful user edits before regeneration.

After native validation, `python3 tools/blender_review/run.py --render-stills` creates
`build/blender_review/cad_review.blend`; add `--open` when requested. The reviewed runtime
is Blender 5.2.2. Verify source/CAD identities and `verification.json` after relevant
changes. Blender checks sampled prescribed rigid motion, not continuous collision,
dynamics, cables, friction or strength. Optical host transfer and powered alignment
are not simulated; optional power is reviewed separately in FreeCAD. Its whole-scene
X half-turn displays neutral optical aim downward without changing native coordinates.
Blender-only edits do not justify promoting the CAD fixture.

## Collaboration and external documents

- Do not re-ask answered questions. Proceed where evidence and authorization suffice;
  ask only for information needed for a remaining decision. Earlier five/ten-minute
  question windows applied to those work sessions, not a permanent question ban.
  Report the result, reasons, checks and material uncertainty concisely in Korean.
- The user has requested reviewed design improvements be pushed to this repository.
  Honor later scope/instructions, preserve others' changes and verify remote state
  before claiming upload success. When asked to show CAD, open the current file/view
  with verified provenance rather than a historical fixture.
- The [Notion plan](https://app.notion.com/p/3e3ee52b5792806c94acc1f798594bad) is auxiliary.
  Improve either it or CAD based on engineering judgment. Discuss proposed Notion
  changes in chat and reach agreement before editing that page; honor existing
  agreement. Do not claim synchronization without actually reading, updating and
  checking the relevant live content.
