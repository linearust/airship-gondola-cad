# Agent operating contract

This file is for AI agents working in this repository. The procurement checklist
below summarizes the current design; keep it synchronized with the authoritative
source definitions and generated BOM instead of treating it as a separate design.

## Authorities

- `gondola/design_contract.py`: scope decisions, nominal rail-length requirement,
  manufacturing decision, equipment selection, evidence
  discrepancies, inventory and unresolved physical interfaces. `python3 -m
  gondola status` reads this contract without FreeCAD or network access.
- `gondola/parts/`: geometry in millimetres. `universal_board.py` owns the board
  dimensions shared by `metric_hardware.py`; `equipment_envelopes.py` contains
  reference envelopes, not printable parts. `fastener_spec.py` owns the shared
  nominal M2 interfaces; do not duplicate hardware dimensions in printed parts.
- `gondola/assembly.py`: native assembly and its expression-driven controls.
  `gondola/cad.py`: shared native metadata and coordinate transforms.
- `gondola/manufacturing.py`: unique part exports and purchased hardware BOM.
  `gondola/validation/`: saved geometry, exports, service paths and baseline checks.
- `gondola/config.py`: artifact schema and pinned regression fixture identity.
  `gondola/provenance.py`: source/artifact hashes. `gondola/bundle.py`: package gates.
- `references/`: retained primary dimension/port/voltage evidence. These files
  are inputs, including images not loaded programmatically. External URLs and
  the Notion edit timestamp record previous evidence, not live verification.
- `tests/fixtures/rev_k_geometry.FCStd`: pinned reviewed reference for geometry
  and native controls. `tests/fixtures/rev_k_review.json` records the deliberate
  Rev J → K changes, source identities and retired fixture in Git history.
  Further geometry revisions require a reviewed replacement fixture and new
  manufacturing/clearance evidence.
  Never regenerate the fixture merely to pass a check.

## Manufacturing decision — Rev K

Decision reviewed 2026-09-20: use **340 mm nominal rail length**, with PA12 **SLS
preferred for the fit prototype** and MJF remaining an alternative. The supplier's
published evidence does not establish that this design requires MJF. This is a
design choice, not physical qualification or a guaranteed maximum as-built length.
`MANUFACTURING_DECISION` in `gondola/design_contract.py` owns this decision.

[Creallo's 2026-05-12 policy](https://creallo.com/ko/blog/posts/sls-mjf-integration-update)
combines SLS/MJF quotes and lets Creallo choose the process; agree SLS separately
when required. Use the same agreed material, process and finish for coupons and
full parts. The [size guide](https://creallo.com/ko/guide/design-spec-guide)
lists SLS 340 × 340 × 600 and MJF 380 × 380 × 280 mm, but includes split-and-join
fabrication. Require confirmation that the rail will be manufactured in one piece.
The stored 45-degree rail export is about 259.14 × 259.14 × 7 mm, leaving about
80.86 mm total X/Y size margin against the 340 mm screen. This is only a size
screen. Even the previous
378 mm rail passed that screen; 340 mm follows the user's preferred length ceiling.

Use a 1.5 mm nominal target for general functional walls, above the 0.8 mm
published minimum. The board keeps a 2 mm deck and 1.8 mm ribs; the journal
D-flat wall, propeller guard and frame service webs are at least 1.5 mm at the
validated sections. Remove redundant grid material instead of thinning these walls.

The 1.2 mm continuous rail base and tape wings remain intentional functional flexures.
This is an explicit exception to the general 1.5 mm target. Reliefs widen from
3 to 4.5 mm to accommodate the thicker flexure; do not claim identical bending
stiffness from the idealized beam approximation.
Shortening the rail does not resolve their manufacturing exception. Creallo's
[wall-thickness guidance](https://creallo.com/ko/blog/posts/importance-of-thickness-in-3d-printing-processes)
applies the long, thin, broad-part recommendation to both SLS and MJF. Obtain
supplier review and test full-rail straightness, balloon curvature, fatigue,
tape retention and sliding/clamping fit; the short coupons cannot prove these.

The seven tape-pad centres and three default module positions remain unchanged.
Pad ends have 1 mm nominal axial margin. Keep the entire 18 mm shoe on the rail:
its centre must stay within ±161 mm, also respecting clamp lands and neighboring
parts. The outermost land centres at ±162 mm are not fully supported shoe stations.
Clamp within 4 mm of a full land centre. Purchased quantities remain 42, but
all designed structural threads are now M2. Preserve the three identical boards.

The scope is the indoor LTA blimp gondola: two main motors, two tilt servos and
MTF-02P are included; yaw propulsion and fins/fin servos are excluded. The optical
sensor faces +Z, away from the balloon plane Z=0. Its conservative optical reserve
must remain clear; verify actual lens datums, wiring and mounting on the purchased
unit. The radio moves 4 mm toward +Y and P-AS moves 1 mm toward −Y; the
conservative optical reserve keeps at least 1 mm nominal clearance to each.

`gondola/mass_budget.py` reports installed print volume × PA12 density and
simplified hardware volume × assumed density. Build metrics and the saved-CAD
validation both contain the budget. Compare structural mass on the same equipment
scope; adding the 1.5 g MTF-02P is not a failed weight reduction. Do not describe
these estimates as measured all-up mass: wiring, adhesive, OEM fasteners and other
unmeasured items remain excluded.

## Procurement checklist

Scope: one gondola's installed parts, excluding spares, printed parts, ground
equipment, charger and balloon. Subtract items already owned or included in
equipment accessory kits before proposing a purchase. These are required design
specifications, not verified seller listings or physical-fit approvals.

Mechanical quantities come from the validated `build/gondola_hardware_bom.json`;
purchase conditions are defined in `gondola/parts/metric_hardware.py`.
The current assembly uses seven purchase types and 42 pieces:

| CAD SKU | Required purchase specification | Installed quantity |
|---|---|---:|
| `M2_MF_30_PLUS_5` | PA66 nylon male/female hex standoff; M2; body 30 mm + male stud 5 mm; across flats 4 mm; usable female thread depth at least 4 mm | 4 |
| `M2X6_SOCKET_CAP` | A2 stainless socket cap screw; M2 × 6 mm; DIN 912 / ISO 4762 | 4 |
| `M2X14_SOCKET_CAP` | A2 stainless socket cap screw; M2 × 14 mm; DIN 912 / ISO 4762 | 4 |
| `M2x6_ISO4026_DIN913` | A2 stainless flat-point socket set screw; M2 × 6 mm; DIN 913 / ISO 4026 | 3 |
| `M2_HEX_NUT` | A2 stainless regular M2 DIN 934 hex nut for stack and journals; across flats 4 mm; height 1.6 mm | 8 |
| `M2_SQUARE_NUT_DIN562` | A2 stainless M2 DIN 562 flat square nut for rail clamps; nominal width 4 mm and thickness 1.2 mm; accepted width 3.6–4.0 mm, thickness 0.8–1.2 mm; verify corner profile | 3 |
| `M2_WASHER_2.2_5_0.3` | A2 stainless flat washer; inside diameter 2.2 mm × outside diameter 5 mm × thickness 0.3 mm | 16 |

All threaded interfaces above are M2 × 0.4, right-hand; washers are unthreaded.
Socket cap screw lengths are measured under the head; the set screw is 6 mm
overall. Retain the flat-point set screw requirement. The 42-piece total excludes
OEM motor/servo fasteners. A separate fit-coupon assembly can borrow one clamp
screw/square-nut pair; add one pair only if it must remain assembled independently.
Each additional equipment-board level needs four more matching standoffs and
reuses the top nuts/washers. The current journal design uses printed sleeves.

Keep the three rail-clamp square nuts separate from the eight stack/journal hex
nuts. A tolerance-small M2 hex nut can rotate inside the 4.6 mm clamp pocket;
do not substitute it for the square nut. [Accu's DIN 562 M2 specification](https://www.accu.co.uk/flat-square-nuts/21324-HFSN-M2-A2)
lists width 4.0–3.6 mm, while [PTS lists 4.0–3.7 mm](https://www.pts-uk.com/products/nuts/square-nuts/metric-a2/a56202).
Both list thickness 1.2–0.8 mm. Use the more conservative 3.6 mm minimum width
for the geometric check, and verify the chosen supplier's actual dimensions.

The rotation screen assumes ±0.3 mm error on the total 4.6 mm pocket width,
giving a 4.3–4.9 mm range. At the minimum pocket, a 4.0 mm nut has 0.3 mm total
insertion clearance. At the maximum pocket, an ideal 3.6 mm square has a 5.0912 mm
diagonal, exceeding the pocket by 0.1912 mm. This margin assumes intact square
corners. Accu describes an unchamfered nut but flags chamfer details as variable;
confirm corner geometry, usable threads and rotational retention with the actual
nut and printed coupon. The screen does not qualify tightening torque, holding
force or the supplier's achieved local tolerance.

Onboard equipment selection comes from `gondola/design_contract.py`:

| Equipment | Selected model or specification | Installed quantity |
|---|---|---:|
| Flight controller with ESC | MicoAir743v2-AIO-35A | 1 |
| Brushless motor | Happymodel RS1102, 10000KV | 2 |
| Propeller | Gemfan 1610, 40 mm, two blades; one CW and one CCW; 1.5 mm shaft-hole variant for the RS1102 shaft | 2 |
| Tilt servo | DSpower DS-M005, 300-degree version | 2 |
| Battery | 2S LiPo, 450 mAh provisional selection; confirm actual dimensions and mass | 1 |
| Optical-flow / range sensor | MicoAir MTF-02P; 21.6 × 16 × 6.5 mm reference envelope | 1 |
| Telemetry module | LR900-A | 1 |
| Positioning module | LinkTrack P-AS | 1 |

The propeller interface is supported by the [RS1102 shaft specification](https://www.happymodel.cn/index.php/2025/01/08/happymodel-rs1102-kv10000-kv13500-brushless-motor-for-micro-fpv-drone/)
and [Gemfan 1610 shaft-hole options](https://www.gemfanhobby.com/40mm-1610-pc-2-blade.html).
The requested 450–2000 mAh battery range does not establish that larger packs fit.
Ground telemetry counterparts and UWB anchors are outside this gondola inventory.

Additional consumables and electrical accessories:

- 12 mm-wide single-sided adhesive tape over each rail wing onto the balloon;
  select adhesive compatibility and final length through the physical fit trial.
- Adhesive hook-and-loop for the battery and electrically insulating mounting
  pads/adhesive for the flight controller and sensor modules.
- One XT30 pigtail and one 220 µF, 35 V capacitor, if absent from the FC kit.
  The CAD reserves are provisional spaces; verify actual component dimensions.
- Flexible wiring, compatible connectors, heat-shrink tubing and strain relief;
  wire gauge, lengths and routing remain to be selected for the electrical assembly.
- Tools if not already owned: 0.9 mm and 1.5 mm hex keys, a 4 mm nut wrench,
  and a wrench matching the selected standoff's 4 mm hex flats.

Unresolved procurement interfaces must remain explicit:

- RS1102 mounting screw diameter, pitch, pattern and safe engagement depth need
  actual motor/vendor confirmation.
- DS-M005 mounting-ear fasteners, supplied 28T horn and horn-retaining screw
  need actual part confirmation. The horn-to-printed-sleeve torque connection is
  unfinished; purchasing the listed hardware alone does not complete it.
- Resolve the stored servo-label rating of 3.7–4.2 V versus the listed 3.7–5 V
  rating against the purchased unit before choosing its power supply/regulator.
  Do not substitute M2 hardware for unspecified OEM fasteners.

When geometry, inventory or equipment selection changes, regenerate and validate
the BOM, then update this checklist in the same change. Do not infer physical
qualification or production release from these quantities or purchase links.

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
