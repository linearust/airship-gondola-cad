# AI agent operating guide

This file and [HANDOFF.md](HANDOFF.md) are for AI agents, not assembly instructions.
Read the latest user request first; it supersedes historical design choices.

BA is the current CAD prototype: [revision review](tests/fixtures/rev_ba_review.json),
[persisted-artifact review](tests/fixtures/rev_ba_artifact_review.json).
The final frozen revision passed 450 native tests and the build, preview,
baseline comparison, validation and bundle sequence. This is not physical or
manufacturing qualification. Earlier AZ and incomplete BA attempts are historical;
check matching fingerprints before using generated files.

## Establish state

1. Inspect Git status and preserve unrelated edits and manually changed CAD.
2. Run `python3 -m gondola status`. The source contracts define the intended design;
   saved CAD and `build/` may be stale. Never infer release status from a filename.
3. Read [HANDOFF.md](HANDOFF.md), the affected source contracts and retained evidence.
   Distinguish seller nominal dimensions, design allowances and physical measurements.
4. Check the revision review and artifact fingerprint before describing a result as
   verified. Earlier successful tests do not validate a later source revision.

## Source map

| Concern | Source |
| --- | --- |
| Revision, layout, inventory, manufacturing basis, unresolved interfaces | [design.py](gondola/contracts/design.py) |
| Bought carbon adapter, evidence and uncertainties | [stack_adapter.py](gondola/contracts/stack_adapter.py), [product review](references/stock_stack_adapter_review.md) |
| FC and confirmed device interfaces | [equipment_interfaces.py](gondola/contracts/equipment_interfaces.py) |
| Navigation, radio and optical alternatives | [equipment_options.py](gondola/contracts/equipment_options.py), [optical_sensors.py](gondola/contracts/optical_sensors.py) |
| Gear, shaft, fastener and horn contracts | [drive.py](gondola/contracts/drive.py), [hardware.py](gondola/contracts/hardware.py), [fasteners.py](gondola/contracts/fasteners.py), [servo_horns.py](gondola/contracts/servo_horns.py) |
| Optional electrical supply | [power_options.py](gondola/contracts/power_options.py), [power review](references/power_module_compatibility.md) |
| CAD geometry and hierarchy | [parts/](gondola/parts/), [assembly.py](gondola/assembly.py), [cad.py](gondola/cad.py) |
| Exports, BOM and mass | [print_export.py](gondola/print_export.py), [procurement.py](gondola/procurement.py), [mass_budget.py](gondola/mass_budget.py), [power_export.py](gondola/power_export.py) |
| Verification and identity | [validation/](gondola/validation/), [tests/](tests/), [config.py](gondola/config.py), [provenance.py](gondola/provenance.py) |

Historical references and revision fixtures preserve the evidence for their own
revision. Old universal 54×74 mm carriers, their carrier-foot interfaces and underside
radio layouts are superseded. BA deliberately uses detachable 25.5 mm carbon-foot
joints; do not restore the older interfaces to satisfy an obsolete assertion.

## Editing boundaries

- Keep shape, native properties, motion controls, reservations, inventory, BOM and
  exports consistent. Use the actual parent frame and shared datums. Device,
  carrier and world orientations are different coordinate systems.
- The paired-servo/input-drive module intentionally remains removable from the
  propulsion/output-bearing frame. Preserve the ordered service path and bearing
  retention; changing a gear-ratio property does not regenerate teeth.
- Check bounded motion, coupled gearing and both ±180° winding states. A static
  clearance envelope is not proof of a moving wire loop, strength or flight safety.
- Retain the three horn profiles and their declared preparation/fastener routes.
  Factory spline and hole axes remain datums. Slots permit alignment before final
  clamping, never running slip. Preserve the OEM centre retaining screw.
- The carbon board is purchased hardware, never a print export. Its conservative
  outline omits undimensioned cutouts and is not evidence of solid support material.
  Use the seller's listed mass independently of that envelope volume. Nominal Ø2
  holes are unthreaded and do not guarantee received M2 clearance. Insulate carbon
  from PCB, solder and wiring. Do not imply all hole patterns can be populated
  simultaneously or that every pattern remains accessible after installation.
- Carbon retention must be rigid independently of FC damping. FC lowest-component
  clearance does not establish the actual PCB bearing plane, damper compression,
  spacer length or complete fastening stack. Preserve these unresolved interfaces.
- Four identical bought carbon adapters carry battery, FC, navigation and Mini
  directly on two PA12 tracks. There are no printed equipment decks, shoes or FC
  saddle. Tape-mounted equipment needs real supported insulating contact; the
  filled carbon envelope does not establish it. Nominal 3 mm padding clears the
  modeled clamp heads; verify compressed clearance and adhesive/strap retention.
- Two downward M2 clamps use each carbon plate's rotated 16 mm Y axes. Bay trim
  is limited to ±6 mm about each bay centre, not about every saved module pose.
  Keep nuts threaded during fine trim; lift/reinstall for coarse relocation.
  Unbolted nuts are not captive. Load them from below before taping the rail;
  tape only external wings. Remove covering equipment before top-clamp access.
- One removable optical portal uses the carbon plate's two 25.5 mm X axes. FC
  reuses its two X-axis studs and raises their intermediate nuts above the feet;
  battery adds two M2×6 pairs. Portal legs at diagonal
  ±24 mm are separate structural datums, not purchased mounting-hole positions.
  Transfer the complete portal/head and recalibrate. Verify staged extraction
  with the fixed portal and other installed modules retained, both optical hosts
  and both sensor profiles. Do not assume upward device extraction through a beam.
- Optional power adds a separate portal and two upper bought carbon plates; it
  does not replace or omit lower carrier obstacles. Optical and power are mutually
  exclusive at one host. Optional hardware is separate from baseline inventory.
  Six carbon boards are installed if all four lower boards and the power option
  are retained; the selected five-piece pack alone is insufficient for that case.
- Validate all local and print-oriented bounds against the 340 mm limit. Published
  Creallo sizes are screening inputs, not guaranteed one-piece acceptance. Qualify
  rail/bearing coupons in the chosen PA12 process; nominal fit does not establish
  insertion force, latch recovery, retention or creep.
- Keep unverified mass, fit, electrical and RF properties explicitly unverified.
  CAD success must not automatically change `design.release_status()`.

## Verification and generated files

For prose-only edits, check evidence, local links and `git diff --check`. For source
changes use Python 3.11+ and run the affected tests before the full native suite:

```sh
uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
uvx ruff==0.16.8 format --check gondola tests build_gondola.FCMacro preview_gondola.FCMacro
python3 -m unittest discover -s tests -v
python3 -m compileall -q gondola
```

Offline tests skip native CAD cases; they do not replace FreeCAD testing. Use
`gondola.freecad_runtime.locate_appimage()` and `mounted_appimage()` to run the native
suite with the mounted AppRun Python and its `usr/lib` on PYTHONPATH. Reviewed
runtime: FreeCAD 1.1.3; investigate kernel changes. `FREECAD_APPIMAGE` overrides the
located image. GUI previews require a display.

Freeze source before generating final artifacts, and stop the sequence on failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola compare
python3 -m gondola validate
python3 -m gondola bundle
```

For another directory pass `--output-dir PATH` before every subcommand. Preview
changes saved display properties and therefore runs before final hash verification.
Inspect assembly, print layout, optical host variants and optional power. Restore
configured selections before saving. Existing GUI documents are not automatically
closed; preserve manual changes before regenerating their underlying files.

The pinned fixture is a regression baseline, not a manufacturing file. Intentional
geometry changes require an independent old/new shape, placement, control and
metadata review before promoting the fixture/checksum. Never update it simply to
hide failures. Source fingerprints cover Python source and root FCMacros, not all
supporting documents/tests; inspect changed evidence separately.

`build/` is generated and ignored. Export only manifest-listed prints. The separate
optional-power CAD and exports must be audited as persisted artifacts, not silently
regenerated during validation. Retain essential evidence and revision review in Git;
Downloads and `/tmp` are not portable evidence stores.

The optional Blender derivative is produced by
`python3 tools/blender_review/run.py --render-stills` after native validation. Its
transform checks concern prescribed rigid motion only; they do not certify contact,
flexible wires, dynamics or strength, and Blender edits do not update native CAD.
