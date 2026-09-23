# Cart adaptation and subsequent mechanical revisions

This is a record of the user-selected cart variants and preparation work, not
a seller certification or an exported bill of materials. Current installed
quantities and exclusions are authoritative in `gondola/contracts/design.py`.
The user authorized adapting CAD to these selected parts. Preserve unresolved
interfaces instead of restoring previous MISUMI/POM or A2 fastener assumptions.

## Selected relevant items

| Cart selection | Design treatment |
| --- | --- |
| M2 482-piece black-steel button-head kit | M2 x 4/5/6/8/10/12/16/20: 30 of each; hex nuts 240; 1.5 mm keys 2. The selected lengths cover the modeled M2 joints. Kit contents are not dimensional certification. |
| Gemfan 1610, 4 pairs Blue 1.5 mm | Corrected bore matches the nominal 1.5 mm RS1102 shaft; main propulsion uses one CW and one CCW. |
| RS1102, 4 PCS 10000KV | Two installed main motors; the other motors are outside gondola scope or spares. |
| KST X06 V6.0, six units | Two tilt servos in CAD; fin servos and spares are outside its scope. Preserve the regular mounting-tab variant. |
| Generic 3 x 6 x 2.5 mm bearings, 10-piece pack | Four installed. Actual race lands, shields, clearance, material and mass remain unverified; do not identify the lot as NSK/ISC MR63ZZ. |
| 6061 nominal 3 x 330 mm rod, five-piece pack | Cut and prepare as below. Diameter tolerance, straightness and temper are unpublished; verify received rod in the bearings and gears first. |
| Kailash 48T / 3 mm and 16T / `3mm3`, three of each | Two pairs installed, one pair spare. The supplied 16T table resolves its bore label to 3 mm. See [gear evidence](kailash_gears_selected_evidence.md) for actual dimensions and remaining material/screw uncertainties. |
| MicoAir743v2 AIO35A, PX4 option | Selected FC/ESC model. Firmware option is not a completed PX4 integration or ground-power test. |
| Tattu 2S 450 mAh 75C | Electrical selection matches; XT30 variant, long-pack dimensions and received mass still need verification. |
| XT30 35 V 220 uF lead | Selected electrical option; actual lead/capacitor envelope, polarity and strain relief remain received-part checks. |
| MTF-02P; LR900-A; XR2 Nano 2.4G | Selected sensor/radio/receiver. LR900-A pack contents and ground-radio availability need checking; XR2 mounting is not yet modeled. |
| SH 1.0 mm connector kit | Subtract supplied device cables. This does not supply the required GH 1.25 mm ends or establish pin order; follow the wiring contract. |

MG-A01 M10 Ultra and the ordinary servo Y harness belong to separate user work
and are excluded from this gondola. Do not introduce either while reconciling
the cart. Other test equipment, the X500/Pixhawk platform, furnishing and balloon
experiments do not define gondola mounting interfaces.

## Rod preparation

| Quantity | Cut length | Flat preparation | Role |
| --- | --- | --- | --- |
| 2 | 24 mm | 5 mm-long local flat starting at the gear end; nominal depth 0.5 mm | Geared output stubs; keep bearing journals round |
| 2 | 14 mm | None | Opposite output stubs |
| 2 | 16 mm | Full-length flat; nominal depth 0.5 mm | Input stubs captured by the horn couplings; no external bearing journal |

Cut square and deburr without enlarging the bearing fit. Cut lengths exclude
saw kerf and finishing allowance. Confirm fit on a sample before preparing the
batch. Clock flats to the actual screws; the photographs do not define their
phase relative to the teeth. The stock-preparation keys and CAD remain the
authority if this table is intentionally revised.

## Fastener adaptation and purchases not covered by the cart

The M2 kit replaces thin square nuts, PA66 screws and rail set screws. Rail
clamps, propulsion structural joints, optical pivots and optical feet use 8 mm
screws; the short radial coupling joints retain 6 mm screws. Revision AF restores
two directly clamped optical feet. The modeled mechanism requires only these
two M2 lengths. No washers are required by the modeled
stacks. A 4.5 mm-diameter by 2 mm-high head cylinder is a **design acceptance
envelope**, not a supplier claim. Measure actual button heads and nuts before
manufacturing. The hex rail seat requires the finished-size range and coupon
checks in `parts/rail.py`; raw PA12 tolerance alone does not qualify capture.

Still needed or unresolved:

- Two KST 0415.13 horns, retaining the proper OEM spline screws. The unmeasured
  plastic horns in the servo box are not automatic replacements.
- Four M1.6 x 8 DIN84 screws and four M1.6 DIN934 nuts for the servo ears;
  inspect actual ear and screw fit. These are separate from the M2 kit.
- Four actual M3 gear set screws, after checking what is supplied. Screw length,
  point, projection and the 48T screw-axis location remain unverified.
- Motor M1.4 screws, FC damping/insulation hardware, P-AS mounting hardware and
  finished harnesses: identify supplied parts and establish safe lengths before
  buying replacements. Their unverified interfaces are not completed by this
  M2 kit or by a passing CAD envelope check.
- The LinkTrack P-AS and compatible ground equipment are not established as
  purchased by this cart. Subtract any already-owned items before ordering.

Previous revision-AA exports do not represent these choices. Release artifacts
must be regenerated from the complete current source and reviewed together; passing
geometry checks never certifies the received hardware or flight readiness.

## Native revision audit

The transition from the pinned revision-AA fixture at commit `fa89db5` was
reviewed before replacing the fixture. All 124 prior shape objects remain;
six bought objects add the two input stubs and their bolt/nut pairs. The
installed print count remains 18 and modeled hardware increases from 62 to 68.
Registry changes contain only those six additions. All native motion/control
expressions remain identical, and bounded control behavior passed.

Intentional geometry changes are the 48T/16T gear envelopes and 16 mm axis
distance, input couplings, output shaft flats, 89 mm half-span/support feet,
M2 kit envelopes, hex rail seats and access corridors, and the reduced 5 mm
output-clamp grip. Servo/horn/propulsor placements follow those dimensions.
The continuous rail, battery/FC/P-AS/LR900/MTF-02P device envelopes and their
connector/service reservations remain geometrically unchanged; phase-wire
loop reservations follow the moved output axes. Material, sourcing and
procurement metadata now describe the selected cart rather than the former
parts. Revision AB represented this authorized design change, not physical
qualification. Revision AC additionally incorporated the reviewed simplification below;
revision AD supersedes its optical tower-foot attachment.

The final AB audit additionally extended the fixed frame's two rail-bolt head
bays by the full 1.2 mm release travel. Only `PropulsionFixedFrame` changed
(27.648 mm3 removed); its bounds, placement and solid count remain unchanged.
All other shapes, native controls, inventory and procurement metadata remain
identical to the reviewed AB assembly. The release sweep checks the complete
headed bolt continuously, including its fully loosened position.


## Revision AC simplification (historical)

The user accepts a modest mass increase in exchange for simpler integral parts
and less sensitivity to noncritical purchased-part outlines. The paired servo
and input-gear module deliberately remains removable. Fixed gear centres,
bearing race contacts, shaft journals and rail nut antirotation remain functional
datums; loosening those interfaces would not be a safe simplification.

- The AC optical base integrated two open 25 mm legs and through-bolt feet.
  Two M2x8 screws and ordinary M2 nuts replace two female/female PA66 columns
  and four M2x5 screws. No blind thread-depth or spacer-across-flats assumption
  remains. Each foot has a short radial slot accepting +/-0.5 mm local axis
  mismatch; this is not an arbitrary position or angle adjustment. Whole-tower
  removal is required for device service on either host: remove the two upper
  nuts and lift it off the retained lower-headed bolts. Install/replace/transfer
  those bolts with the carrier off the rail on a bench; downward bolt extraction
  on the assembled rail would meet the tape/envelope region. Device lift paths
  must retain the two bolts as obstacles.
- The optical head's two independent manual alignment pivots, shared host axes,
  sensor location and field-of-view reservations are unchanged. The provisional
  capacitor allocation moves 6 mm outward in X to clear the integral tower on
  the electronics host; its full reserved size is retained.
- Servo body windows increase from 8x21 to 9x21.5 mm without reducing their
  nominal 2 mm sidewalls or changing ear mounting axes and gear centres.
- Horn pockets use straight relieved blade flanks. The root register and flat
  tip stop retain their functional finish-fit datums: actual horn root size,
  overall tip reach and coaxiality still require checking. A closed rear hub
  ring was rejected because it cannot pass over an already retained horn.
- Bearing caps retain their locating features and assembly splits. The rail's
  standard M2 nut capture retains its coupon/finished-fit requirement; replacing
  it with an open tool slot would introduce a cantilever reaction wall and a
  specially thin holding-tool requirement.

Installed printed part count remains 18; modeled purchased hardware decreases
from 68 to 66 pieces and from 14 to 12 types. M2x5 and separate optical columns
are no longer required. This count excludes the unmodeled device fastening
stacks and other items identified above. Nominal CAD checks do not establish
received-part fit, tower stiffness or strength.

The modeled structure/hardware estimate changes from 82.653 to 83.297 g
(+0.644 g): printed PA12 volume adds approximately 1.706 g, while removal of the
separate columns and changed fasteners subtracts approximately 1.061 g. These
are common-assumption CAD estimates, not measured product masses or an all-up
flight mass. Source density/material and omitted-hardware limits remain in the
exported mass budget.

The AC fixture transition is recorded in `tests/fixtures/rev_ac_review.json`.
Only the integral optical base, paired servo bridge, two horn adapters and
capacitor reservation changed geometry; every retained object placement and
native motion expression stayed unchanged. Four foot hardware objects replace
six old stack hardware objects. The final 128-shape comparison, 258 native
FreeCAD tests, both 25-attitude optical host checks, assembly/equipment service
and manufacturing screens, export identity and prototype bundle checks passed.

## Revision AD optical attachment

The AD trial (superseded by AF) replaced its two M2x8 screws and two M2 nuts with
integral positive hooks and open host seats. Refer to
[latch attachment review](latch_attachment_review.md) for the release mechanism,
clearance tradeoff and mandatory same-process coupon checks. The paired servo
module and all preload-dependent mechanism joints retain their fasteners.
Current counts and release status come from `gondola/contracts/design.py`;
the AC quantities and 25 mm tower described above are historical.

## Revision AE handling robustness

The user accepts modest mass increases for simpler, less delicate structures.
The four tall output-bearing posts now have plain 9.6 x 4 mm web sections;
their unnecessary lightening windows are removed. The separate low wire/key
corridors, bearing seats, shaft locations, fasteners and removable servo bridge
remain unchanged. No purchased interface is resized. CAD screening includes
complete output rotation and the existing axial-travel allowance.

The optical head's pivot ears, narrow connecting post and tray neck increase
from 1.5 to 2 mm. Its two pivot screws change from M2x6 to the already-selected
M2x8 kit size. At AE the tower latches retained their separately specified flexible
sections; AF subsequently removed them. Part count,
sensor datum and angle controls remain unchanged. The selected gear report now
distinguishes the 3 mm driver face, 5 mm output face and 3 mm nominal overlap.

The modeled print and fastener mass increases by approximately 3.21 g under
the existing density assumptions; this is not measured or all-up mass.
Physical stiffness, screw fit, retention and pointing still require the
existing prototype checks. The intentional geometry and metadata transition is
recorded in `tests/fixtures/rev_ae_review.json`; current quantities remain in
`gondola/contracts/design.py` and the generated BOM.

AE verification passed 262 native FreeCAD tests without skips, complete saved
assembly/equipment and propulsion checks, 126-shape fixture comparison, native
controls, print-export identity and prototype bundle checks. These are CAD and
consistency results, not physical strength or fatigue qualification.

## Revision AF optical seating and motion review

The AD/AE latch allowed 0.7 mm nominal seating play, up to 1.3 mm under its
dimensional allowance. Its unspecified anti-rattle pad did not establish a
stable optical datum. AF removes the fingers and guide features; two broad
integral feet now contact their host directly and are clamped with the existing
M2x8 screws and M2 nuts. No new fastener type or washer is introduced. Remove
these four fasteners before lifting the complete tower; the current outboard
axes clear modeled parts during downward screw extraction. Detach the host
carrier for bench service: the balloon is not modeled and may block underside
tool access. Reinstall the carrier and re-trim afterward. Confirm received screw bearing faces, thread diameter, print flatness and clamp
retention. The remaining clearance-hole registration is a pre-tightening
position allowance, not permissible operating wobble.
The provisional capacitor reservation moves another 2 mm outward in X to
preserve a service margin across the permitted seated tower registration.
Its full Ø10 x 16 mm allowance is retained; no actual capacitor mount is implied.

The horn motion audit now excludes only the actual nominal spline projection
from horn/servo contact, separately checking the full case and mounting ears.
Bearing outer-ring caps remain because the examined shaft rings and collars
do not replace their housing-retention function; see
[bearing retention review](retention_review.md). No propulsion geometry or
purchased drivetrain interface changes in AF. Current quantities and unresolved
physical checks remain authoritative in the contracts and generated BOM.
