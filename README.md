# AI agent guide

Sole agent guide. Later user instructions take precedence. Before editing, inspect
Git status and `python3 -m gondola status`; preserve unrelated edits and manual CAD.
Read the affected source contracts and retained evidence, not historical chat alone.

## Design intent

- Lightweight LTA gondola: favor simple, printable, inspectable structure over small
  weight savings. Integrate unless assembly, motion or replacement benefits from a split.
- Prefer suitable bought metric parts and few fastener varieties. Accommodate real
  fit variation without operating looseness or elaborate adjustment mechanisms.
- Consider wiring, moving clearances, assembly access and balance together. Favor
  reusable mounting interfaces and simple exact simulation datums where feasible.
- Existing geometry is replaceable. Preserve the intentionally detachable paired
  servo/input-drive module and already-purchased bearing size unless instructed otherwise.

## Scope and evidence

Gondola, two independent tilt propulsors and onboard mounts; fins and aft yaw hardware
are excluded. Tape the rail to the envelope; optical sensing must remain relocatable
and unobstructed downward. Creallo PA12 is the manufacturing basis; process/finish
remain unconfirmed. Every printed part must fit within 340 mm on each local and
exported axis. The rail's tape attachment base must be at least 1.5 mm nominal.

Selections, quantities, dimensions and unresolved issues belong in source, not
copied tables here:

- [Design contracts](gondola/contracts/design.py): scope, manufacture, inventory,
  layout and release limitations; other [contracts](gondola/contracts/) define interfaces.
- [Geometry](gondola/parts/), [assembly](gondola/assembly.py),
  [validation](gondola/validation/) and [tests](tests/).
- [Final cart evidence](references/cart_selected_parts_2026-09-29.json),
  [cart/CAD interpretation](references/cart_adaptation_review.md),
  [manufacturer horn provenance](references/manufacturer/kst_x06_servo_horns_2026-09-28.json)
  and [horn interface](references/servo_horn_compatibility.md).
- [Rail fit](references/rail_fit_review.md), [rail joint](references/rail_joint_review.md),
  [bearing retention](references/bearing_keeper_review.md),
  [layout/wiring](references/layout_and_wiring_review.md).

Distinguish user confirmation, catalog geometry, design allowance and measurement.
A cart is selection evidence, not proof of delivery or exact fit. Preserve relevant
source contents/provenance in Git; URLs alone are insufficient. Keep only current
working references and regression fixtures; Git history holds superseded records.

CAD success does not qualify printed fit, strength, creep, adhesive, wiring,
electrical/thermal operation, installed mass/CG or flight. Read `release_status()`
before readiness claims. Qualify fit coupons with the production material/process/
finish and feature orientation; check actual bearings, shields and fastener engagement.

## Change and verification workflow

Update affected geometry, native controls/parents, interfaces, BOMs, service/motion
reservations and checks together. Preserve ordered assembly/removal and moving-wire
paths. Test full travel and identify sampled versus continuous clearance evidence.
Never replace the pinned fixture merely to make a failing comparison pass: intentional
changes require independent old/new shape, placement, control and metadata review.

Documentation-only edits need consistency/link checks and `git diff --check`, not
CAD regeneration. For code changes, run Ruff and relevant tests. For a CAD release,
run native FreeCAD unittest discovery with no skips for `tests`,
`tools/blender_review` and `tools/simulation`. The launcher in
[freecad_runtime.py](gondola/freecad_runtime.py) locates/mounts the installed AppImage;
use its `AppRun python` with the repository and `usr/lib` in `PYTHONPATH`.

Freeze source, then run in order, stopping on failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola compare
python3 -m gondola validate
python3 -m gondola bundle
```

`build/` is generated and ignored, not a fixture. Preview saves CAD, so it precedes
file-bound checks. Inspect assembly, print layout and affected detail views. Preserve
native station settings. Keep a concise file/source-bound verification record in Git;
old successful reports do not validate new source. See the
[current verification](references/design_verification.json). `--output-dir PATH` precedes the
subcommand and must be consistent across steps. Export only manifest-listed prints;
optional power artifacts are separate from the baseline inventory.

After CAD changes, refresh dependent deliverables:

```sh
python3 tools/blender_review/run.py --render-stills
python3 tools/simulation/export_parameters.py
```

Blender checks prescribed rigid motion, not dynamics, flexible wires or strength.
The [simulation sheet](references/simulation_parameters.md) separates exact CAD
geometry from unmeasured vehicle inputs; native coordinates are not automatically
CV/FRD coordinates. Recheck saved-file hashes when presenting an artifact.
