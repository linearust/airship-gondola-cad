# AI agent guide

Later user instructions take precedence. Inspect Git status and
`python3 -m gondola status` before editing; preserve unrelated edits and manual CAD.

## Design intent

- Favor low total mass and simple, printable, inspectable construction. Integrate
  parts unless assembly, motion or replacement benefits from separation.
- Prefer available metric parts, reusable interfaces and few fastener types.
  Accommodate fit variation without operating looseness or elaborate adjustment.
- Consider wiring, moving clearances, optical visibility and balance together.
  Improve existing geometry on merit, respecting confirmed purchases and intentional
  replaceable modules.

Scope: indoor LTA gondola, two independent tilt propulsors and onboard mounts;
fins and aft yaw hardware are excluded. Current manufacturing limits and selections
are in [design.py](gondola/contracts/design.py), not duplicated requirements here.

## State and evidence

[Contracts](gondola/contracts/), [parts](gondola/parts/) and
[assembly](gondola/assembly.py) define intended CAD, not measured hardware.
Read `release_status()` for unresolved interfaces. [Sources](references/sources.json)
index retained originals and dated user records. Distinguish source statements,
user confirmation, design allowances and measurements; resolve conflicts explicitly.
Preserve original evidence and provenance, not URLs alone. Keep changing dimensions
and generated inspection sheets out of maintained prose.

[Verification](references/design_verification.json) records a past execution, valid
only for its inputs. `source_fingerprint()` covers Python under `gondola`, root
macros and `gondola/data`; tests, tools and documents need separate change/hash checks.
CAD success does not establish physical fit, strength, creep, adhesion, wiring,
power, installed mass/CG or flight readiness. Qualify coupons using production
material, process, finish and feature orientation.

## Workflow

Update affected geometry, native controls/parents, interfaces, BOMs and motion/service
checks together. Review full travel and ordered removal; distinguish sampled from
continuous checks. Fixture replacement requires independent old/new shape, placement,
control and metadata review, never merely a new checksum to hide a failure.

Documentation-only changes: check links, JSON, source records and `git diff --check`.
Code changes: Ruff and relevant tests. CAD release: native FreeCAD unittest discovery
with no skips for `tests`, `tools/blender_review` and `tools/simulation`.
[Runtime launcher](gondola/freecad_runtime.py) locates the AppImage; use its
`AppRun python` with repository and `usr/lib` in `PYTHONPATH`.

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

`build/` is generated/ignored. Preview saves CAD, so it precedes file-bound checks.
Inspect assembly, print layout and affected views. For `gondola`, `--output-dir PATH`
precedes the subcommand; keep output/source paths consistent across tools. Export manifest-listed
parts, distinguish optional power parts, and retain hash-bound verification.

Optional paired rail/frame/saddle fit specimen: after validation, run
`python3 tools/fit_coupon/export_joint.py --output-dir PATH` with a new directory.
It crops saved production geometry; it is outside the installed BOM/print bundle
and tests local fit, not whole-frame strength or complete-assembly tool access.

Blender checks prescribed rigid motion, not dynamics or flexible wires. Simulation
geometry is exported to `build/simulation_parameters.json`; unknowns remain unset.
Native coordinates are not CV/CG or FRD. Recheck hashes before presenting artifacts.
