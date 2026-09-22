# Drivetrain selection review — 2026-09-22

Existing dimensions are not design constraints. Compare complete mechanisms for
this indoor LTA gondola, including couplings, retention, printability and mass.

## Selected prototype

The current MISUMI gears, Ø3 shafts and MR63ZZ bearings retain a documented
round-bore/set-screw torque path. Their fits, clamping and loaded operation are
still unqualified. They are retained for that simpler specified connection,
not because a smaller redesign would be inconvenient or Ø2 steel is inherently
too weak. Current purchase specifications remain in `gondola/contracts/hardware.py`.

## Credible smaller candidate, not an order substitution

- [KHK DS catalog](https://khkgears.net/pdf/ds.pdf): DS0.5-48 driver and DS0.5-15
  output give ratio 3.2 and nominal centre distance 15.75 mm. Nominal bores are
  Ø5 and Ø2; published reference masses are 1.91 and 0.23 g. The 48T gear has
  a different axial stack from the selected MISUMI gear. The DS bores have
  −0.05 to −0.30 mm deviation; no supplied set screw is specified. KHK advises
  avoiding secondary machining because molded voids may occur. A nominal bore
  is not proof of a safe retaining press fit. The 16T alternative has a Ø3 bore.
- [KSSC Super Shaft](https://www.kssc.co.jp/catalog/SHAFT_pack.html): 2025 h7 and
  2014 h7, two each, are Ø2 SUS304 shaft candidates. The 25 mm part cannot replace
  the existing 24 mm driven stub without checking the whole axial stack. No
  factory flat is specified; h7 is not a guaranteed bearing slip fit.
- [EZO MR52ZZ](https://www.ezo-brg.co.jp/english/product/spec.php?eid=00077):
  2 × 5 × 2.5 mm, 0.19 g reference mass; four required. Housing shoulders and caps
  must suit its own race/shield geometry.

These gears, shafts and bearings total approximately 6.98 g, versus 12.71 g in
the present CAD/catalog estimate: about 5.74 g gross opportunity. This mixes
reference masses and calculated steel/gear volumes; new couplings, retention,
supports and actual specimens determine the net result. It is not a promised
whole-gondola saving. Four separate stubs still avoid the motor bay.

Ø2 steel is plausible under the intended light loads; stiffness ratios alone
do not reject it. Adoption requires a simple concentric horn connection and
verified output torque/axial retention using the actual molded gears. Do not
add sleeves, custom tiny screws or unapproved gear machining merely to claim
the gross saving. Qualify one complete interface chain before changing the
selected CAD, BOM and fixture together. No directly splined X06-compatible
spur gear has been verified by this review.

A further stock route exists: [Robinson Racing 1820](https://robinsonracingproducts.com/rrp-hi-performance-parts-2mm-bore-motor-pinions/)
is a hardened-steel 20T module-0.5 pinion with Ø2 bore and a supplied 5-40 set
screw (1/16-inch Allen key). The manufacturer's page does not specify pressure
angle, face/hub/overall dimensions, bore tolerance or mass. It is a drawing/sample
candidate, not a verified MISUMI-compatible or lighter replacement. No suitable
manufacturer-specified split Ø3-OD/Ø2-ID reducer was verified; do not assume a
plain tube transmits torque reliably when crushed by the existing set screw.
