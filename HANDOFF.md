# Temporary AI handoff — delete after takeover

Snapshot: 2026-10-02. This is a transfer note, not a permanent specification or
an instruction to freeze the design. Later user instructions and inspected source
take precedence. After completing the takeover steps below, delete this file and
commit its deletion. Do not copy this whole snapshot into README or create another
handoff automatically. No source code or build step depends on this file.

## Latest user direction

- For future user-requested CAD changes, improve the design on merit. No CAD
  redesign or finalization task is currently pending. The earlier attempt to
  finalize printing, quotation and inspection documents is no longer active.
  In particular,
  **do not resume or recreate the CC delivery/PDF work** unless newly requested.
- Remove obsolete generated deliverables that could be mistaken for current
  geometry. Keep authoritative source evidence and reviewed regression fixtures.
- This turn changes documentation and removes obsolete outputs only; it does not
  change the verified CD geometry or assert fabrication readiness.

## Repository and verified snapshot

- Workspace: `/home/h/cad/airship-gondola-cad`.
- Remote: `https://github.com/linearust/airship-gondola-cad.git`.
- Branch at handoff: `codex/square-carriers`; inspect actual Git state on arrival.
- Last **CAD/code** commit: `6cc3ab4766394ad9bfab42d29a72c3065c66c0ab` (CD).
  The subsequent handoff/cleanup commit does not change CAD source. Do not reset
  the branch to the CAD commit or discard later user edits.
- Source fingerprint: `590003a963e695faa575eabbfcd5955827af488a98d1132a7f15d1348bec4bf6`.
- Saved assembly SHA-256: `b6498e73f051d2f04c5996ca0a6193f8841233df4dec517c2dcd9473b7946feb`.
- Approved fixture SHA-256: `1a746039cafbb4c27de3beb0f62fae5b3513de028ce1061eef30b59bb0c9a99c`.

[design_verification.json](references/design_verification.json) records **809 native
tests passed, zero failures/errors/skips**, six passing CAD validation reports,
the build/preview/compare/validate/bundle pipeline, Blender and simulation export.
Blender checked six prescribed rigid-motion scenes, 1,229 sampled frames and
90,184 matrices, with no discrepancies. This is not dynamics, flexible-wire,
strength or physical-fit validation. The checks were executed for the recorded
inputs; the documentation-only handoff did not rerun them.

The full hash-bound record is in [design_checks.json.gz](references/design_checks.json.gz),
key `cd_contact_and_horn_revision`. It embeds the independent old/new fixture
review and exact intermediate audit evidence. Historical paths inside that record
are provenance, not current delivery locations or work to resume. Do not delete
the fixture, source originals or this verification evidence as “legacy.”

## What the last CAD change actually did

- Added selected root fillets and exposed-edge rounding while protecting mating
  surfaces, bores and minimum stock. Installed printed **volume** increased about
  0.303%; this is not measured mass or a strength improvement measurement.
- Ordinary universal-carrier shoes now bear on the local rail-wall top: the old
  nominal 0.7 mm roof gap is removed. Lower legs have 1 mm base clearance. Their
  intended straight-rail trim remains ±3 mm per station. They follow the local
  wall pitch; this does not qualify a level rigid deck across an arbitrary curved
  rail. The paired propulsion joint still uses its separate crowned-contact design.
- The selected manufacturer **X06 supplied plastic half arm 1 is unmodified**.
  No horn drilling, tapping or forcing an oversized screw is intended. The adapter
  provides a Ø1.2 round opening at radius 6.8 mm, a 1.2 × 1.6 mm optional slot at
  10 mm, and a 1.2 × 1.8 mm slot at 13.2 mm. Two end fasteners per horn are the
  installed default; the middle opening is not a qualified three-bolt assembly.
  The fourth OEM hole, Ø0.8 at radius 4.5 mm, is not an M1 passage.
- User owns **M1 metric external-hex bolts/nuts**, but supplied no actual lengths,
  head/nut dimensions or material. M1×6 is a design length, not an ownership claim.
  Acceptance envelopes: head AF ≤2.5 mm and height ≤1 mm; ordinary nut AF 2.4–2.5 mm
  and height ≤0.8 mm. A 2.6 mm-wide shallow nut trough permits insertion while
  resisting rotation. These bounds do not establish compatibility with every M1
  variant. Actual M1 must slip through the OEM nominal Ø1 holes. Equal nominal
  diameters do not guarantee clearance. Servo-ear M1.6 and motor M1.4 fasteners
  are separate interfaces; do not replace them wholesale with M1.
- The final validation also corrected conservative rounded-shape bounds and an
  optical-tray service sweep. Blender mesh placement now uses trimmed BRep bounds
  with the existing 0.08 mm tessellation limit; its axial-basis numeric comparison
  alone accepts 1e-6 mm precision. Physical motion limits were not enlarged.

For current numbers and service order use [servo_horns.py](gondola/contracts/servo_horns.py),
[servo_coupling.py](gondola/parts/servo_coupling.py), and the corresponding validation
modules. Do not revive the previous M1.4/M1.6 horn-hole enlargement scheme.

## Design intent and active choices

Read [README.md](README.md) for persistent intent. This is a lightweight indoor LTA
gondola with two main tilting propulsors; fins and aft yaw hardware are out of scope.
Prefer simple printable integral shapes, common metric parts, symmetric support,
few fasteners and snug located joints. Nuts should enter freely and resist rotation.
Modest extra mass is acceptable for simpler, stronger or less fit-sensitive parts.
Keep the **paired servo/gear module separate from the propulsion frame** for future
replacement. Separation does not mean every servo or gear variant already fits.

Current architecture uses printed side-slot rail and universal carriers. Earlier
carbon-adapter-board/tube-rail concepts and generic aftermarket horn proposals are
not the active baseline. Preserve confirmed purchases rather than reselecting them
from old conversation proposals:

- KST X06, selected stock OEM horn, metric module-0.5 48T driver / 16T driven gears,
  both Ø3 mm bores; four purchased 3 × 6 × 2.5 mm bearings and nominal Ø3 rod.
  Bounded output target ±180°; no continuous wrap. Another ratio/servo requires
  replacement-part design and renewed checks, not a claim of drop-in compatibility.
- MicoAir H743V2 AIO **45A AM32**. User confirmed 2S operation; do not reopen that
  selection from older 35A-board documentation. Installed supply/load tests remain.
- LR24-F-Mini airborne radio; LR24-F is on the ground. LR900-A support was removed.
  Navigation alternatives share a location with P-AS; optical choices are MTF-02P
  or MTF-01P. Read [equipment_options.py](gondola/contracts/equipment_options.py),
  [optical_sensors.py](gondola/contracts/optical_sensors.py), and
  [power_options.py](gondola/contracts/power_options.py) before changing selections.
- Unfilled PA12 is the design basis; Creallo SLS/MJF process, grade and finish are
  not finalized. Maximum part dimension 340 mm; rail currently 300 mm. Rail base
  and tape wings retain the supplier-feedback minimum of 1.5 mm. Do not confuse
  fillet radii, nominal contact fits or printed tolerance allowances with proven
  delivered fit, flexibility, creep or fatigue performance.

The retained OEM archive/STEP provenance is in
[the manufacturer record](references/manufacturer/kst_x06_servo_horns_2026-09-28.json).
[sources.json](references/sources.json) indexes the final cart, supplier feedback
and other evidence. Old purchase records are dated evidence, not an overriding
current BOM; the later M1 horn decision is an example. Keep source facts, user
confirmation, chosen envelopes and unmeasured quantities distinct.

## Unresolved facts that must not become assumed confirmations

Read `release_status()` in [design.py](gondola/contracts/design.py) for the full list.
The design remains `fit_prototype`, with `production_released = false`.

- Actual RS1102/Gemfan seating and full blade axial sweep are unknown; the user
  cannot currently measure them. The motor carrier remains **QUOTE_ONLY / fabrication
  hold**. The displayed propeller plane and collision-free reference case are not
  proof of the installed rotor clearance. Other mounts can still be developed.
- M1 slip fit, actual hardware length/tool access, horn seating/runout, bearing/rod
  fits, gear set-screw protrusion, PA12 contact fits and loaded retention need real
  assembly checks. Gear set-screw solids are not yet modeled. Keep the intentional
  bearing/shaft allowance; do not remove it by preloading bearing shields.
- Wiring reserves are planning envelopes; moving-wire routing, optical visibility
  after relocation, electrical load/thermal margins, installed mass/CG and flight
  readiness are not established by CAD. Pi 5/A8 patterns do not qualify their loads.

## Local artifacts and cleanup

Current local snapshot: `/home/h/Downloads/airship_gondola_CD_2026-10-02/` contains
`gondola_CD.FCStd`, `print_parts_CD.zip`, `assembly_CD.png`, and a hash manifest.
It is a verified development snapshot, **not a final manufacturing release**.
No current drawing PDF is supplied. After further changes these outputs become
stale; do not use the folder name alone to establish currency.

The obsolete Downloads **CB and CC folders were deleted**, along with old generated
quote/drawing work, obsolete unversioned power exports, old joint coupons, old
mechanism-video renders, old review scratch folders and generated FreeCAD backups.
Tracked source/evidence, approved fixtures, current CD artifacts, current Blender
review and current validation/audit outputs remain. Git retains prior source history;
the deleted generated packages need not be restored. An already-open FreeCAD window
can still contain an old in-memory document: open a provenance-checked current file
explicitly rather than trusting window recency, and do not overwrite manual edits.

`build/` and Downloads are local/generated, not guaranteed to exist on another
account or machine. Current canonical generated assembly is `build/gondola.FCStd`;
the paired-joint coupon, if needed later, must be regenerated from current geometry.
For regeneration and validation follow README. FreeCAD is available on this host
at `/home/h/Applications/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage`; use
[freecad_runtime.py](gondola/freecad_runtime.py) rather than assuming system Python
provides FreeCAD. Blender is handled by `tools/blender_review/run.py`.

## Takeover and deletion

1. Read README; inspect Git status, branch, recent commits and remote state. Preserve
   unrelated or manual edits. Read this snapshot against the actual files.
2. Inspect current contracts, `python3 -m gondola status`, verification inputs and
   source hashes. Do not rerun the full CAD release merely to read this handoff.
   After relevant edits, run appropriate tests; a new CAD release follows README.
3. Acknowledge that prior CC finalization/PDF work is cancelled and physical-fit
   unknowns remain. Do not invent a new CAD task or regenerate cancelled deliverables.
4. Once the context is understood, **delete `HANDOFF.md` and commit its deletion**.
   Keep durable intent in README and dimensions/evidence in their existing source
   locations. Only newly discovered durable omissions belong there; do not preserve
   this temporary snapshot as another permanent document.
