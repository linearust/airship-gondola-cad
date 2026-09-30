# AI agent guide

Later user instructions take precedence. Before editing, inspect Git status and
`python3 -m gondola status`; preserve unrelated edits and manual CAD.

## Intent and scope

- Lightweight indoor LTA gondola: prefer simple, integral, printable structure over
  small weight savings. Use suitable bought metric parts and few fastener varieties.
- Accommodate fit variation without operating looseness. Consider wiring, motion,
  assembly access and balance together; favor reusable interfaces and exact datums.
- Redesign freely, preserving the intentionally detachable paired servo/input-drive
  module and purchased bearing size unless instructed otherwise.

Scope: gondola, two independent tilt propulsors and onboard mounts; excludes fins and aft yaw
hardware. Tape the rail to the envelope. Optical sensing must remain relocatable
and unobstructed downward. Creallo PA12 is the basis; process/finish are unconfirmed.
Printed parts must fit within 340 mm on each local and exported axis; the rail's
tape attachment base must be at least 1.5 mm nominal.

## Authority and evidence

[Contracts](gondola/contracts/), [geometry](gondola/parts/) and
[assembly](gondola/assembly.py) own current selections, dimensions, allowances,
service sequences and BOMs. Read `release_status()` in
[design.py](gondola/contracts/design.py) for unresolved interfaces.

[Retained sources](references/sources.json) index original evidence and dated
user records. Distinguish catalog statements, user confirmation, CAD allowances
and measurements. A cart is not a receipt; generic parts are not certified by a
different maker's catalog. Preserve source contents and provenance, not URLs alone.
Do not duplicate changing design values in prose or commit generated inspection
sheets. Git history holds superseded explanations.

[Verification record](references/design_verification.json) is a past execution
bound to its source/file hashes, not perpetual approval or verification of later
documentation. CAD checks do not qualify physical fit, strength, creep, adhesion,
wiring, electrical operation, installed mass/CG or flight. Match fit coupons to
the production material, process, finish and feature orientation.

## Change and verification

Update affected geometry, controls/parents, interfaces, BOMs and motion/service
checks together. Review full travel and ordered removal. Distinguish sampled from
continuous clearance evidence. Fixture replacement requires independent old/new
shape, placement, control and metadata review; never replace it to hide a failure.

Documentation-only edits: check links, retained hashes and `git diff --check`;
do not regenerate CAD. Code changes: Ruff and relevant tests. CAD releases:
native FreeCAD unittest discovery with no skips for `tests`, `tools/blender_review`
and `tools/simulation`. [Runtime launcher](gondola/freecad_runtime.py) locates the
AppImage; use its `AppRun python` with repository and `usr/lib` in `PYTHONPATH`.

Freeze source; run in order and stop on failure:

```sh
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola compare
python3 -m gondola validate
python3 -m gondola bundle
python3 tools/blender_review/run.py --render-stills
python3 tools/simulation/export_parameters.py
```

`build/` is generated/ignored. Preview saves CAD and must precede file-bound checks.
Inspect assembly, print layout and affected views. `--output-dir PATH` precedes
the gondola subcommand and must stay consistent. Export manifest-listed parts;
optional power artifacts are separate. Retain concise hash-bound verification.

Blender checks prescribed rigid motion, not dynamics or flexible wires. Simulation
values come from `build/simulation_parameters.json`; keep unknowns unset and do
not equate native coordinates with CV/FRD. Recheck hashes before presenting files.
