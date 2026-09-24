# Selected cart and preparation work

This records the user's selected parts and preparation decisions, not seller
certification or a shopping list. The selected purchased interfaces are retained
through the rail layout and shared equipment-support changes; see
`layout_and_wiring_review.md` and `shape_simplification_review.md`.
Use exports and inspection material matching the
current saved CAD and source. This does not qualify the received parts or prepared horn.
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
| KST X06 V6.0, regular mounting tabs | Two tilt servos. Use their supplied horns and original spline screws; fin servos and spares are outside this CAD. |
| Generic 3 x 6 x 2.5 mm ball bearings | Four installed. Actual race lands, shields, internal play, fit, material and mass remain unverified. Do not identify the received lot as NSK/ISC MR63ZZ. |
| Selected nominal Ø3 mm 304 rods | Prepare the six shafts below. The user accepts replacing unsuitable stock with precision shafts; nominal size does not establish a fit tolerance. |
| Kailash 48T / 3 mm and 16T / `3mm3` | Two pairs installed. The supplied 16T table resolves its bore label to 3 mm. See [gear evidence](kailash_gears_selected_evidence.md); do not restore the old MISUMI/POM assumptions. |
| MicoAir743v2-AIO-45A AM32 | Replaces the cart's former 35A Bluejay board by user decision. Same nominal mechanical interface; official 2S/3S input claims conflict. See [controller evidence](controller_selection_review.md). Firmware, power compatibility and the supplied mounting stack remain unverified. |
| Tattu 2S 450 mAh 75C, XT30 | Long-pack dimensions, leads and received mass still require inspection. |
| XT30 lead, 35 V / 220 µF capacitor | Inspect actual envelope, polarity and strain relief. |
| MTF-02P; LR900-A; XR2 Nano 2.4G | Selected sensor/radio/receiver. MTF-01P can replace MTF-02P on the same adhesive tray; install one only, as described in `optical_sensor_compatibility.md`. Check supplied cables and ground-radio availability; XR2 mounting is not modeled. |

The user will not purchase bearing spacers. AM uses direct frame-side capture
of the ball-bearing outer rings; no HIROSUGI spacer, 3 x 5 x 3 mm oil-free bush,
ordinary washer or push-on shaft ring replaces it. The rejected bush touches
the selected bearing shield. Do not enlarge the assembly to accommodate it or
accept shield contact as a thrust interface. See [retention](retention_review.md)
for the process-coupon and assembly requirements.

MG-A01, the ordinary servo Y harness, push-on retaining-ring kit and nylon M2
standoff kit are outside this purchasing/design change. Other test equipment,
X500/Pixhawk hardware, furnishings and balloon experiments do not define
gondola mounting interfaces. FC/P-AS support stacks remain separate unresolved
interfaces; the bearing-spacer decision does not delete those requirements.

## Rod preparation

| Quantity | Cut length | Flat preparation | Role |
| --- | --- | --- | --- |
| 2 | 24 mm | 5 mm-long flat from the gear end; nominal depth 0.5 mm | Geared output stubs; keep bearing journals round |
| 2 | 14 mm | None | Opposite output stubs |
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

The supplied-horn adapter is a workshop-prepared blank, not a part that assumes
the purchased horn has the old KST 0415.13 outline or a 13.2 mm tip hole. Retain
the genuine spline and OEM screw. Check actual horn geometry and complete the
centred, two-hole preparation described in [retention](retention_review.md).
There is no separate horn purchase requirement. Its material and mass remain
unknown; a null mass is not a zero-mass part or a demonstrated mass saving.

Still establish from the received parts:

- Four M3 gear set screws: supplied contents, lengths, points, projection and
  the 48T screw-axis position are unverified.
- Motor M1.4 screw engagement, FC damping/insulation and fastening stacks,
  P-AS support/fastening stacks and finished harnesses. Use owned/supplied
  hardware first; only identified shortfalls justify purchases.
- LinkTrack P-AS and compatible ground equipment: this cart does not establish
  their purchase. Subtract already-owned equipment before ordering.

The checked rail L-key envelope remains a tool compatibility requirement;
compare the supplied tool with [rail access](rail_joint_review.md). Geometry
checks do not certify received hardware, printed spring recovery or flight
readiness. The AM fixture was updated after the native old/new geometry and
metadata audit. Future changes require a new audit and regenerated release
artifacts from one frozen source. Earlier assembly methods belong to Git history,
not current instructions.
