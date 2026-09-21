# Agent operating contract

This file is for AI agents. Keep design decisions, procurement requirements and
validation gates synchronized with source and generated artifacts. It is not a
human assembly manual or a declaration of physical qualification.

## Authorities

- `gondola/design_contract.py`: scope, revision, inventory and unresolved evidence.
  `python3 -m gondola status` works without FreeCAD or network access.
- `gondola/parts/mounting_interfaces.py`: published electronic mounting patterns,
  sources and explicit unknowns. Never infer PCB bearing planes from box heights.
- `gondola/parts/equipment_mounts.py`: compact battery support and open electronics
  carrier. `equipment_envelopes.py`: purchased-device envelopes and reserves.
- `gondola/parts/wiring_clearance.py`: connected FC routing reservation and
  connector-access lanes; dimensions are design allowances, not installed ports.
- `gondola/parts/propulsion.py`: frame, carriers, custom torque journals and the
  published servo/motor interface decisions. `rail.py`: shared rail/shoe/clamp.
- `gondola/parts/fastener_spec.py`: common purchased M2 dimensions.
  `metric_hardware.py`: the six modeled mechanism hardware purchase types.
- `gondola/assembly.py`: assembly and native expression controls.
  `cad.py`: metadata and local/world transforms.
- `gondola/manufacturing.py`: unique print exports and hardware BOM.
  `validation/`: saved geometry, motion, mounting, service and export checks.
- `gondola/config.py`: artifact schema and pinned regression identity.
  `provenance.py` and `bundle.py`: source/artifact hashes and package gates.
- `references/`: retained primary evidence, including drawings used by agents.
- `tests/fixtures/`: one reviewed pinned CAD reference and its transition audit.
  Older fixtures remain in Git history. Never regenerate a fixture merely to
  pass a failing comparison; audit deliberate shape, placement and scope changes.

## Rev N decisions

Scope remains one indoor LTA blimp gondola: two main propulsors, two tilt servos,
FC, battery, LR900-A, LinkTrack P-AS and MTF-02P. Yaw propulsion, fins and fin
servos are excluded. Preserve bounded independent tilt of +/-150 degrees.

The user's latest instruction supersedes the previous identical-board and
no-device-holes requirements. Remove the three 64x76 universal boards, unused
upper rail shoe and tall four-post expansion stack. Keep two role-specific
printed mounts: a 16x52x2 mm continuous battery adhesive deck and one open
carrier connecting only the required electronic mounting pads and adhesive
surfaces. Both integrate the shared rail shoe; do not add separate adapter
fasteners without a demonstrated benefit.

Confirmed interfaces and conservative design reservations are distinct:

| Device | CAD implementation | Unresolved; do not invent |
|---|---|---|
| MicoAir743v2-AIO-35A | Official 25.5x25.5 mm pattern, diameter3 mm device holes, 45-degree orientation; carrier has four diameter2.6 mm M2 clearance holes with continuous diameter6.5 mm pads | PCB bearing-plane Z, rubber groove/OD/compressed height, exact spacer and screw lengths |
| LinkTrack P-AS | Official two diameter2.2 mm device holes, 23 mm pitch, 6.7 mm from connector-side edge; carrier has diameter2.6 mm M2 clearance holes | PCB bearing-plane Z, actual fastening stack; datasheet7 mm vs drawing5.3 mm height conflict |
| DS-M005 | Official ear axes: 19.50 mm pitch and -5.82/+13.68 mm relative to output axis; ear underside10.20 mm from case bottom. Open U-saddles use those axes and preserve material around them | Case-to-axis offset, ear thickness, bolt length and actual seating; supplied 28T horn geometry and retaining screw |
| RS1102 10000KV | Official three M1.4 threads on PCD6.6 recorded as evidence; no newly generated motor fastening holes | Rear shaft/clip keepout and safe insertion depth. Adding closed clearance holes beside the existing diameter4.4 relief leaves only about0.2 mm ligament; do not manufacture this thin wall or guess a smaller rear keepout |
| LR900-A | Small continuous insulating adhesive pad; no invented holes | No confirmed hole pattern; listed29.5x13x9 mm excludes SMA socket, antenna and plugged cables |
| MTF-02P | Small continuous insulating adhesive pad; no invented holes; optical face points away from balloon (+Z) | Backside contact, connector access and lens datums |

The FC manufacturer supplies four **M2x7.5 mm silicone dampening sleeves**.
Use those bought parts; do not print substitute dampers or an unverified spline.
DS-M005's drawing lists16.05x8.30x17.20 mm while the current product table lists
16.2x8.3x17.4 mm. Retain the larger case reservation; the published ear axes and
10.2 mm underside datum are separate evidence, not proof that all supplied units
match both sources. RS1102 radial packaging includes the drawing's maximum
diameter13.6 mm (nominal13.5 +0.10).

The model allocates **8 mm below the full FC envelope** above the carrier face.
An8x8 mm X-open wiring corridor is offset to Y=5..13 mm so it avoids
all four FC attachment axes. Rev N joins that corridor to a5 mm outward-normal
peripheral band and two continuous diameter3 mm exit turns with5 mm centreline
radius. These are planning envelopes, not selected wire diameters, manufacturer
bend limits or a completed harness. The peripheral band covers the FC body
height plus1 mm at both Z faces; it reserves connector/housing space, not a full
FC unplug stroke. Select purchased
spacers and fasteners after measuring the real PCB/damper stack; preserve the
reserved lower-envelope clearance. P-AS has4 mm nominal service space below its
conservative7 mm envelope. Its antenna is toward+Y and remains exposed.

Move LR900-A from module Y36 to41 mm and MTF-02P from Y-39 to-46 mm. Only their
existing support arms become longer; do not enlarge all supports or change the
confirmed FC/P-AS mounting axes. The placement keeps at least1 mm nominal
separation between the expanded FC reservation and neighboring devices/optics.
The MTF displacement includes its conservative42-degree optical field, not
merely the gap between bare boards.

Reserve15 mm along both LR900-A long-axis ends,15 mm outward from the P-AS
19 mm connector band at-Y, and12 mm outward from the MTF's full16 mm edge at+X.
The MTF layout deliberately adopts its drawing's connector-edge orientation;
match the actual board and firmware rotation. Exact port XYZ, latch positions,
USB plugs and SMA/antenna geometry remain unverified. Use the P-AS side-entry
port for this allowance; its parallel top-entry port is not an additional load.
Disconnect leads before the validated bare-device lift or module slide paths.

The XT30 allocation is10x42x15 mm, with mating axisY: a central10x22x15 body
space and10 mm pull/lead space at each end. [AMASS XT30U drawings](https://www.china-amass.com/biao/268.html)
give a maximum mated envelope of5.9x20.6x10.5 mm in this orientation. The extra
travel is our allowance, not a published disengagement stroke; actual battery
connector variant, heat-shrink, cable bend and mounting remain to check.
Motor slack-loop reservations move to X=-38 mm, behind the neutral motor and
outside the complete rotor bound. They remain isolated planning volumes, not
connected moving-wire routes or proof of cable safety through+/-150 degrees.

References: [FC manual](https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-35a-manual),
[FC included parts](https://store.micoair.com/wp-content/uploads/2026/05/MicoAir743v2-AIO-35A_spec6.webp),
[P-AS drawing](https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf),
[confirmed DS-M005 product](https://www.dspowerservo.com/ds-m005-mini-servo-product/),
[RS1102 drawing](https://www.happymodel.cn/wp-content/uploads/2025/02/RS1102-KV10000.jpg).

Simplify frame load paths and remove redundant material without thinning
functional walls below1.5 mm. The custom D journals remain because they transmit
torque into the carriers as well as supporting rotation. A generic purchased
bearing is not a direct replacement: it still needs correctly supported races,
axial retention and the unpublished OEM horn interface. Do not add a speculative
bearing/shaft conversion merely to replace a custom part with more parts.
The electronics carrier uses 5x2 mm cantilever arms. Its solid connectivity and
clearance checks do not establish stiffness, vibration resistance or adhesive
retention; verify those with the actual supported devices.

## Manufacturing and mass

PA12 SLS is preferred for the fit prototype; MJF remains an alternative. Rail
nominal length is **340 mm**. Its stored45-degree print envelope is approximately
259.14x259.14x7 mm. This is a size screen, not as-built dimensional certification.
[Creallo combines SLS/MJF quotations](https://creallo.com/ko/blog/posts/sls-mjf-integration-update)
and normally chooses the process; agree a specific process and one-piece rail
manufacture separately. Use the same material/process/finish for coupons and parts.

Use1.5 mm nominal functional walls,2 mm mounting decks and the validated section
sizes. The1.2 mm rail base/tape wings are an explicit functional-flexure exception,
not blanket compliance with [Creallo's broad thin-part guidance](https://creallo.com/ko/blog/posts/importance-of-thickness-in-3d-printing-processes).
Retain18 mm land pitch,4.5 mm reliefs and0.5 mm root fillets: these features enable
curvature and protect flexure roots rather than merely decorating the part.
Supplier review, full-rail bending/fatigue, tape retention and loaded clamp/journal
tests remain required. A short coupon does not qualify the full rail.

Keep every18 mm shoe fully on the rail: centre |X|<=161 mm, also respecting
neighbors and clamp lands. Clamp within4 mm of a full land centre. The outermost
pad/land centres at+/-162 mm are not fully supported shoe stations. Rail wings
still use single-sided tape OVER the wings; no tape beneath the rail or across
its running head. The shared shoe retains both selectable clamp directions.

`mass_budget.py` reports printed BRep volume x PA12 density and simplified bought
mechanism volume x assumed material density, compared with reviewed Rev K.
**FC/P-AS mounting spacers/dampers/fasteners and OEM motor/servo fasteners are not
fully dimensioned or included.** The modeled saving is not the final net saving
after those new attachment parts are bought. Wiring, adhesive, antenna and other
unmeasured items are also excluded; never call this a measured all-up mass.

## Procurement contract

Prefer standard parts purchasable on AliExpress. The generated BOM includes
precise requirements and AliExpress search links. Searches and manufacturer
examples are not verified seller options, stock, delivery or supplier-lot fit.
Do not print bought fasteners, ordinary spacers, dampers, servo horns or devices.
Actual selected seller options must match the dimensional specification.

Modeled mechanism hardware: **six types,26 pieces**, excluding spares and device
mounting kits whose lengths/bearing planes remain unresolved:

| CAD SKU | Required specification | Quantity |
|---|---|---:|
| `M2X14_SOCKET_CAP` | A2 stainless M2x14, DIN912/ISO4762, under-head length14, head diameter3.8/height2, hex key1.5 mm | 4 |
| `M2_HEX_NUT` | A2 DIN934 M2x0.4, AF4/height1.6 mm; journal retention only | 4 |
| `M2_WASHER_2.2_5_0.3` | A2 washer ID2.2 x OD5 x thickness0.3 mm; four under heads and four under nuts | 8 |
| `M3_WASHER_3.2_9_0.8` | A2/SUS304 DIN9021 / ISO7093-1 large washer ID3.2 x OD9 x thickness0.8 mm; added inner retainers on M2 bolts | 4 |
| `M2x6_ISO4026_DIN913` | A2 M2x6 flat-point set screw, DIN913/ISO4026, hex key0.9 mm | 3 |
| `M2_SQUARE_NUT_DIN562` | A2 M2 square nut, nominal width4/height1.2 mm; accepted width3.6–4.0/height0.8–1.2 mm, verify corners | 3 |

Diameter5 mm washers and M2 nuts can pass through the carrier D-bore together
with the sleeve. Use one bought large washer per journal between sleeve and the
small nut-side washer. Keep the small washer: M2 nut across-flats is not its
bearing-face diameter; its chamfered bearing face may not span the large bore.
The M3 washer designation is an unthreaded clearance size; all mechanism bolts
remain M2. Do not replace the large retainer with another small washer.

[JC Fasteners B4D0303009](https://www.jcfasteners.com/wp-content/uploads/DIN-9021-Large-Washer-B4D03-SS304.pdf)
specifies ID3.20–3.38, OD8.64–9.00 and thickness0.70–0.90 mm. Nominal CAD checks
must include the entire fastened stack resisting axial escape, washer-to-sleeve
and nut-side contact, free rotation and removal after disassembling fasteners.
The D-flat is essential for capture; a round bore is not an equivalent geometry.
Dimensional screens do not qualify tilted/eccentric bearing, deformation,
preload, friction, wear or vibration loosening.
[JC's small M2 washer](https://www.jcfasteners.com/wp-content/uploads/DIN-125-Plain-Washer-B4D02-SS304.pdf)
has ID2.20–2.34, OD4.70–5.00 and thickness0.25–0.35 mm.
[Böllhoff DIN934 A2](https://eshop.boellhoff.de/out/media/pdf/DIN_934_Edelstahl_A2___en.pdf)
gives M2 minimum bearing-face diameter3.2 mm. The small washer bridges that
face to the larger washer; across-flats alone would miss the nut chamfer.

The rail clamps require square nuts; do not substitute small hex nuts.
[Accu](https://www.accu.co.uk/flat-square-nuts/21324-HFSN-M2-A2) permits minimum
width3.6 mm while [PTS](https://www.pts-uk.com/products/nuts/square-nuts/metric-a2/a56202)
lists3.7 mm. The check uses3.6 mm and a4.6 mm pocket with+/-0.3 mm size error:
minimum insertion clearance0.3 mm, theoretical45-degree blocking margin0.1912 mm.
Verify actual corners, usable threads, torque and retention with the coupon.

Onboard devices: MicoAir743v2-AIO-35A x1; RS1102 10000KV x2; Gemfan1610 40 mm,
1.5 mm bore, CW/CCW x1 each; DS-M005 300-degree x2;2S450mAh XT30 battery x1
(dimensions/mass provisional); MTF-02P x1; LR900-A x1; LinkTrack P-AS x1.
Subtract items already owned or included in equipment kits. Yaw/fin/ground
hardware is outside this inventory.

Additional purchased attachment parts are required, **not completed BOM rows**:
FC has four M2 attachment locations with its included dampers; P-AS has two M2
locations; each servo has two diameter1.8 mm ear holes suitable for a designed
M1.6 clearance fastening, not an identified OEM screw. Select actual spacer,
washer, nut and screw lengths only after their bearing planes are known. Motor
mounting is still unresolved despite its confirmed M1.4 pattern. No generated
part substitutes for the supplied28T horn or its retaining screw.

Consumables remain12 mm single-sided compatible tape, battery hook-and-loop,
insulating adhesive pads for LR/MTF, flexible wire/connectors/heat-shrink/strain
relief, one XT30 pigtail and one220uF35V capacitor if absent from the FC kit.
Keep optics, antenna regions and FC ESC cooling surfaces clear. Servo supply
voltage3.7–4.2 V on the stored label versus3.7–5 V on the confirmed product page
remains a source discrepancy; verify the actual supplied unit before powering it.

`design_contract.WIRING_PURCHASE_PLAN`, also embedded in the hardware BOM's
explicitly unmodeled requirements, records three UART harnesses:

| Connection | Purchased connector ends | Quantity |
|---|---|---:|
| FC UART1 to LR900-A | SH1.0-6P to GH1.25-4P | 1 harness |
| FC UART3 to P-AS | SH1.0-6P to GH1.25-4P | 1 harness |
| FC UART4 to MTF-02P | SH1.0-4P to SH1.0-4P | 1 harness |

Buy matching pre-crimped pigtails or housing/contact kits; subtract included
cables. These are connector-end requirements, not verified ready-made cable
pinouts. SH/GH families are not interchangeable and a matching pin count does
not imply straight-through wiring. Use the official pinouts, TX/RX mapping and
supply requirements; the FC's separate DJI six-pin port supplies12 V.
[JST SH](https://www.jst-mfg.com/product/pdf/eng/eSH.pdf) and
[JST GH](https://www.jst-mfg.com/product/pdf/eng/eGH.pdf) housing dimensions are
retained as primary evidence, without claiming that a marketplace clone matches.

Use bought nylon ties with strap width at most2.5 mm at existing frame windows
and arms for fixed lead retention. Keep heads outside the moving mechanism and
leave phase-loop slack; actual tie/head fit, quantity and wire retention remain
to verify. No printed connector shells, cable clips, ordinary spacers or horns
are added. The custom rail/shoe, lightweight ribs and D torque journals retain
functions that an off-the-shelf bearing does not replace by itself.

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
Artifact schema2 requires explicit release/procurement scope and BOM hash binding;
regenerate older exports instead of reusing their reports.
Export checks bind each part's installed/coupon quantity to the native registry.
BOM purchase fields must match every native instance; its explicit scope excludes
unmodeled device mounting kits. Native release status and frozen part purchase/print
roles are checked independently of geometry.
CI also checks imports and formatting with Ruff 0.16.8 and `ruff.toml`; run
`uvx ruff==0.16.8 check gondola tests build_gondola.FCMacro preview_gondola.FCMacro`
and the corresponding `format --check` before uploading source changes.

`build/` is the only default generated directory and is ignored by Git. Its
`gondola.FCStd`, `gondola_print_parts/print_manifest.json`, validation JSONs,
previews and `gondola_print_parts.zip` are reproducible outputs, not source.
`gondola_wiring.png` shows the electronic wiring reservations in translucent
orange; those volumes must never become printable parts or verified cables.
Use `--output-dir PATH` before the command consistently for a separate run.
Do not commit build trees, duplicate archives, machine logs or temporary mounts.
GUI entry points are `build_gondola.FCMacro` and `preview_gondola.FCMacro`.

## Change constraints

- Keep source evidence separate from design allowances. Only confirmed mounting
  axes may become holes; unknown Z dimensions or thread depths stay unresolved.
- Preserve shared shoe capture, both clamp approaches, bounded independent tilt,
  service paths, optical clearance and the explicit FC wiring corridor.
- Geometry revisions need a documented old/new shape and native-control audit,
  then a newly pinned fixture. Never add a comparison exception to conceal damage.
- Print only manifest-listed parts. Hardware/equipment/reserves stay excluded.
- Source changes invalidate generated reports: rebuild, preview, validate, compare
  and bundle for the same source/CAD/exports. Never copy a previous success report.
- CAD success does not establish friction holding force, strength, electrical
  compatibility, physical mounting-stack fit or flight readiness.
