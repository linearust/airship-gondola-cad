# Agent operating contract

This file is for AI agents working in this repository. Do not turn it into a
human-facing project guide or duplicate generated dimensions/BOM tables here.

## Authorities

- `gondola/design_contract.py`: scope decisions, equipment selection, evidence
  discrepancies, inventory and unresolved physical interfaces. `python3 -m
  gondola status` reads this contract without FreeCAD or network access.
- `gondola/parts/`: geometry in millimetres. `universal_board.py` owns the board
  dimensions shared by `metric_hardware.py`; `equipment_envelopes.py` contains
  reference envelopes, not printable parts.
- `gondola/assembly.py`: native assembly and its expression-driven controls.
  `gondola/cad.py`: shared native metadata and coordinate transforms.
- `gondola/manufacturing.py`: unique part exports and purchased hardware BOM.
  `gondola/validation/`: saved geometry, exports, service paths and baseline checks.
- `gondola/config.py`: artifact schema and pinned regression fixture identity.
  `gondola/provenance.py`: source/artifact hashes. `gondola/bundle.py`: package gates.
- `references/`: retained primary dimension/port/voltage evidence. These files
  are inputs, including images not loaded programmatically. External URLs and
  the Notion edit timestamp record previous evidence, not live verification.
- `tests/fixtures/rev_i_geometry.FCStd`: immutable pre-refactor reference for
  geometry and native controls. Never regenerate it merely to pass a check.

## Execution

Use Python 3.11+ for the CLI and offline checks. CAD commands require an installed
FreeCAD with its bundled Python, Part, Mesh and MeshPart modules. The Linux CLI
mounts an existing FreeCAD AppImage, locating it under `~/Applications` or
`~/Downloads`; override with `FREECAD_APPIMAGE` or `--freecad-appimage PATH`.
Preview additionally requires a working graphical display. The workflow was
exercised with FreeCAD 1.1.3; a different kernel may need geometric investigation.

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q gondola
python3 -m gondola status
python3 -m gondola build
python3 -m gondola preview
python3 -m gondola validate
python3 -m gondola compare
python3 -m gondola bundle
```

Preserve this order: preview saves native display properties and therefore
changes the CAD file hash. Source changes require rebuilding before preview and
validation. Any failed command stops the sequence. Both validation and baseline
comparison must pass for the exact current source/CAD/exports before bundling.
The offline tests and GitHub CI do not perform CAD geometry validation.
CI also checks imports and formatting with Ruff 0.16.8 and `ruff.toml`; run
`uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro`
and the corresponding `format --check` before uploading source changes.

`build/` is the only default generated directory and is ignored by Git. Its
`gondola.FCStd`, `gondola_print_parts/print_manifest.json`, validation JSONs,
previews and `gondola_print_parts.zip` are reproducible outputs, not source.
Use `--output-dir PATH` before the command consistently for a separate run.
Do not commit build trees, duplicate archives, machine logs or temporary mounts.
GUI entry points are `build_gondola.FCMacro` and `preview_gondola.FCMacro`.

## Change constraints

- Keep native object names and expressions stable during code-only refactors;
  the baseline comparison exercises every saved shape and native control.
  A deliberate geometry change needs an explained baseline change and new evidence.
- Use shared metadata, transforms, schema and hash helpers. Preserve local,
  world and print coordinate distinctions; do not mutate cached shapes.
- Print only manifest-listed parts. Purchased hardware, equipment envelopes and
  clearance reserves remain excluded. Quantities belong to generated manifests.
- Keep physical/OEM interfaces unresolved until their required evidence exists.
  Passing CAD checks does not establish loaded operation, manufacturing approval,
  electrical compatibility or complete flight mass.
- Keep generated success reports tied to current source and artifact hashes.
  Never bypass package gates or copy old reports into a new build.
