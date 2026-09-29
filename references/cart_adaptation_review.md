# Selected cart and preparation work

Retained saved-cart snapshot: [2026-09-27 selected options and findings](cart_review_2026_09_27.json).
It covers the 91 product rows actually present in the supplied HTML; the page's
92-item header does not reconcile to those rows. This is not a live-stock check
or proof that the complete live cart was captured. Unrelated stock and spare
quantities do not define additional installed devices.

This records the user's selected parts and preparation decisions, not seller
certification or a shopping list. The selected purchased interfaces are retained
through the rail layout and shared equipment-support changes; see
`layout_and_wiring_review.md` and `shape_simplification_review.md`.
Use exports and inspection material matching the
current saved CAD and source. This does not qualify the received parts or horn coupling.
Current installed quantities belong to `gondola/contracts/design.py` and the matching
generated BOM, not the cart pack counts.

## Selected parts and exclusions

| Selection | Design treatment |
| --- | --- |
| Owned M2 482-piece black-steel button-head kit | Eight lengths and hex nuts cover the modeled M2 joints. Do not request another purchase. Measure the actual heads/nuts against the declared design envelopes. |
| Selected M1.4/M1.6 Phillips kit, assorted lengths | Use received screws after checking head envelope, usable engagement and tool access. Do not ask for the length inventory again or identify this kit as DIN84 slotted screws. |
| Owned GH1.25 and selected SH1.0 connector kits | Subtract supplied cables before preparing harnesses. Connector families do not establish pin order or voltage. |
| Gemfan 1610, 1.5 mm bore | Two main propellers, one CW and one CCW. Match the actual RS1102 shaft. |
| RS1102 10000KV | Two main motors in this CAD; aft motor and spares are outside gondola scope. |
| KST X06 V6.0, regular mounting tabs | Two tilt servos; fin servos and spares are outside this CAD. Both use manufacturer stock plastic half arm 1; see the [current horn interface](servo_horn_compatibility.md). Earlier metal-horn variants are historical. |
| Generic 3 x 6 x 2.5 mm ball bearings | Four installed. Actual race lands, shields, internal play, fit, material and mass remain unverified. Do not identify the received lot as NSK/ISC MR63ZZ. |
| Selected nominal Ø3 mm 304 rods | Prepare the six shafts below. The user accepts replacing unsuitable stock with precision shafts; nominal size does not establish a fit tolerance. |
| Kailash 48T / 3 mm and 16T / `3mm3` | Two pairs installed. The supplied 16T table resolves its bore label to 3 mm. See [gear evidence](kailash_gears_selected_evidence.md); do not restore the old MISUMI/POM assumptions. |
| MicoAir743v2-AIO-45A AM32 | Replaces the cart's former 35A Bluejay board by user decision. Same nominal mechanical interface; user confirmed 2S support on 2026-09-29. See [controller evidence](controller_selection_review.md) for retained historical catalog disagreement. Actual firmware, installed power behavior and the supplied mounting stack remain unverified. |
| Tattu 2S 450 mAh 75C, XT30 | Long-pack dimensions, leads and received mass still require inspection. |
| XT30 lead, 35 V / 220 µF capacitor | Inspect actual envelope, polarity and strain relief. |
| MTF-02P; LR24-F-Mini; XR2 Nano 2.4G | Current sensor/radio/receiver selection; the earlier cart LR900-A is superseded. MTF-01P can replace MTF-02P on the same adhesive tray; install one only, as described in `optical_sensor_compatibility.md`. Check supplied cables and ground-radio availability; XR2 mounting is not modeled. |

The user will not purchase bearing spacers. The current design uses direct frame-side capture
of the ball-bearing outer rings; no HIROSUGI spacer, 3 x 5 x 3 mm oil-free bush,
ordinary washer or push-on shaft ring replaces it. The rejected bush touches
the selected bearing shield. Do not enlarge the assembly to accommodate it or
accept shield contact as a thrust interface. See [retention](retention_review.md)
for the process-coupon and assembly requirements.

MG-A01 was excluded from the original cart adaptation, but the later AR user
decision adds MG-A01/M10 Ultra and bare MG-F10-A as alternatives to P-AS on the
shared navigation support. It is no longer a blanket CAD exclusion; see
[navigation compatibility](navigation_module_compatibility.md). The same later
AT scope supports only LR24-F-Mini onboard, with LR24-F on the ground; see
[radio compatibility](radio_module_compatibility.md).

The ordinary servo Y harness, push-on retaining-ring kit and nylon M2
standoff kit remain outside this purchasing/design change. Other test equipment,
X500/Pixhawk hardware, furnishings and balloon experiments do not define
gondola mounting interfaces. FC/P-AS support stacks remain separate unresolved
interfaces; the bearing-spacer decision does not delete those requirements.

## Rod preparation

| Quantity | Cut length | Flat preparation | Role |
| --- | --- | --- | --- |
| 2 | 34 mm | 5 mm-long flat from the gear end; nominal depth 0.5 mm | Geared output stubs for the current 150 mm axis spacing; keep bearing journals round |
| 2 | 20 mm | None | Opposite output stubs |
| 2 | 18 mm | Full-length flat; nominal depth 0.5 mm | Input stubs; no external bearing journal |

Lengths exclude saw kerf and finishing allowance. Cut square and deburr;
confirm received-stock fit in the bearings and gears before preparing a batch.
Do not assign an unpublished h5 tolerance. Clock flats to the actual screws;
photos do not establish their phase relative to gear teeth. Encoded preparation
keys and the final CAD remain authoritative if the interfaces change.

## Fasteners and preparation

The mechanism uses M2 button-head screws of 8 mm and 6 mm length with one M2
hex-nut family. The short radial shaft joints use the 6 mm screws. No washer
is required by the modeled stacks. The Ø4.5 x 2 mm M2 head cylinder is a design
acceptance envelope, not a measured or published kit dimension. Inspect actual
head bearing faces, nut capture and rail contact; qualify the finished rail
nut-seat range with the matched coupon.

The M1.6 Phillips screws have their own declared head envelope in
`contracts/fasteners.py`. The actual head, tool fit and safe thread engagement
must fit the receiving joint. Their use does not establish OEM motor screw
depth or the supplied horn's central retaining-screw specification.

The current adapter uses manufacturer stock half arm 1 on both sides. Enlarge its
existing Ø1 mm pilots at radii 6.8/13.2 mm to Ø1.5 mm, preserving their axes;
use two rear M1.4×8 screws and front M1.4 nuts per horn. The adapter has a near
round hole and a far short tolerance slot. Servo-ear screws and M1.6 nuts are
separate joints. See [horn compatibility](servo_horn_compatibility.md).
Alignment allowance is for assembly before tightening, not running slip. Actual
horn mass, finished fit and loaded coupling retention remain unverified.

Still establish from the received parts:

- Four M3 gear set screws: supplied contents, lengths, points, projection and
  the 48T screw-axis position are unverified. The user already accepted buying
  these later; do not present that deferred item as a newly discovered blocker.
- Motor M1.4 screw engagement, FC damping/insulation and fastening stacks,
  P-AS support/fastening stacks and finished harnesses. Use owned/supplied
  hardware first; only identified shortfalls justify purchases.
- The current saved cart includes MG-F10 and M10 Ultra navigation alternatives.
  P-AS is not a missing required purchase when using one of them; the CAD's
  default P-AS reference is not a demand to purchase all supported alternatives.
  Ground equipment and a complete installed antenna/tether harness are outside
  the evidence of nominal onboard product selections.

The checked rail L-key envelope remains a tool compatibility requirement;
compare the supplied tool with [rail access](rail_joint_review.md). Geometry
checks do not certify received hardware, printed spring recovery or flight
readiness. Intentional geometry changes require a new native old/new audit
and regenerated artifacts from one frozen source. Earlier assembly methods belong to Git history,
not current instructions.
