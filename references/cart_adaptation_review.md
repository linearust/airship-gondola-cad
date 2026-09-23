# Selected cart and preparation work

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
| 2 | 18 mm | Full-length flat; nominal depth 0.5 mm | Input stubs captured by the horn couplings; no external bearing journal |

Cut square and deburr without enlarging the bearing fit. Cut lengths exclude
saw kerf and finishing allowance. Confirm fit on a sample before preparing the
batch. Clock flats to the actual screws; the photographs do not define their
phase relative to the teeth. The stock-preparation keys and CAD remain the
authority if this table is intentionally revised.

## Fastener adaptation and purchases not covered by the cart

The M2 kit replaces thin square nuts, PA66 screws and rail set screws. Rail
clamps, propulsion structural joints, optical pivots and optical feet use 8 mm
screws; the short radial coupling joints retain 6 mm screws. The optical feet
are directly clamped. The modeled mechanism uses these two M2 lengths;
prepared horn-tip joints share the servo-ear M1.6 hardware. No washers are
required by the modeled stacks. A 4.5 mm-diameter by 2 mm-high head cylinder is a **design acceptance
envelope**, not a supplier claim. Measure actual button heads and nuts before
manufacturing. The hex rail seat requires the finished-size range and coupon
checks in `parts/rail.py`; raw PA12 tolerance alone does not qualify capture.

Still needed or unresolved:

- Two KST 0415.13 horns, retaining the proper OEM spline screws. The unmeasured
  plastic horns in the servo box are not automatic replacements. Enlarge only
  the existing tip hole at radius 13.2 mm from nominal 1.0 mm to 1.8 mm, supporting
  the blade and deburring without countersinking. This is local preparation,
  not a factory hole or a qualified strength change. Inspect for distortion
  and cracks and verify the assembled joint under bidirectional load.
- M1.6 x 8 DIN84 screws and M1.6 DIN934 nuts for both servo ears and
  prepared horn-tip joints; use the current quantities in the generated BOM
  and inspect actual hole, head and nut seating. These are separate from the M2 kit.
- HIROSUGI F3035-5105T flanged metal bearing spacers. These replace the
  printed caps and their fasteners; verify received bearing lands and assembled
  endplay. The catalog minimum is 50 pieces and Korean supply is unconfirmed.
  See [retention review](retention_review.md).
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

The AH rail/head and bearing-post-root revision retains these purchase
quantities. Its 1.5 mm L-key access uses the short arm at the propulsion frame
and the long arm at equipment carriers; compare the supplied kit tool with the
checked envelope in [rail joint review](rail_joint_review.md).

The subsequent AJ close-fit rail and central servo revision preserve this purchase selection;
see `references/shape_simplification_review.md`. Current release changes are
audited in `tests/fixtures/rev_aj_review.json`.
Earlier geometry and assembly instructions remain in Git history and the
versioned fixture reviews; they are not current build instructions.
