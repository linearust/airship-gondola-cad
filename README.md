# AI agent operating guide

This file and [HANDOFF.md](HANDOFF.md) are for AI agents, not assembly instructions.
Read the latest user request first; it supersedes historical design choices.

AZ verification is recorded in [the revision review](tests/fixtures/rev_az_review.json)
and [the persisted-artifact review](tests/fixtures/rev_az_artifact_review.json).
The frozen revision passed 448 native tests without skips and all five artifact
stages. These are CAD checks, not physical fit or manufacturing approval; later
source edits require fresh matching evidence.

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
revision. In particular, old universal 54×74 mm carriers, optical foot clamps and
underside radio layouts are superseded by the purchased-adapter redesign. Do not
restore them merely to satisfy an obsolete assertion or document.

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
  simultaneously or that the installed saddle leaves every pattern accessible.
- Carbon retention must be rigid independently of FC damping. FC lowest-component
  clearance does not establish the actual PCB bearing plane, damper compression,
  spacer length or complete fastening stack. Preserve these unresolved interfaces.
- Role carriers share a rail interface rather than an oversized identical deck.
  Tape-mounted equipment needs supported insulating contact, not a perforated
  carbon envelope assumed to be solid. Retain real device holes where documented;
  omit dedicated tie-only slots and tabs.
- The selected optical portal is fused into its carrier. A host change requires the
  appropriate replacement carrier; transfer the movable head and recalibrate.
  Do not invent a detachable tower or upward removal through its fixed beam.
  Verify staged device extraction, both optical hosts and both sensor profiles.
- Optional power uses an integral replacement carrier, not a duplicate carrier
  stacked on the original. Exclude only that replaced print from interference
  checks. Optical and power upper structures are mutually exclusive at a host.
  Optional prints/boards are separate from the default installed inventory.
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
python3 -m gondola validate
python3 -m gondola compare
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
