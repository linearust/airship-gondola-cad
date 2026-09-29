# BI design review

Intent: mount the optical head on an existing universal carrier and balance
output support with gear-module and rotor replacement space. The nominal main
motor axes remain 150 mm apart and 50 mm below the rail contact plane. These are
actual CAD dimensions, not rounded simulation exports. The paired servo/input
module remains separate from the output-bearing frame.

## Carrier-mounted optical head

A rectangular 8 × 16 × 2 mm foot uses the middle side slot of the existing
64 mm universal carrier. Two M2×8 screw/nut pairs, 10 mm apart, clamp the foot;
one more M2 pair locks the single ±20° pitch joint. There is no dedicated optical
rail shoe or additional carrier. The straight post and adhesive tray remain two
prints, with no new latch, shim or adjustment mechanism. This adds one ordinary
M2 pair relative to BH while removing the independent rail interface.

The default host is the battery carrier's +X edge: world X117 mm, pivot Z35 mm.
Native +Z points downward/away from the balloon. Z30 was screened and rejected
because the larger MTF-01P/connector could meet the maximum battery envelope at
negative pitch; Z35 clears the selected sensor options in the checked layout.
Both MTF-02P and MTF-01P use the same adhesive tray.
For the illustrated direct-tether arrangement, transfer the same foot to the
existing accessory carrier NegativeX edge: world pivot (−131, −0.1, 35) mm.
The battery is absent; no extra printed carrier or different pedestal is needed.
This direct-tether optical arrangement accepts P-AS, MG-A01 and MG-F10-A with
remote SMA antenna. The direct MG-F10-A helix obstructs the optical assembly/field
and is rejected in this arrangement; its battery-baseline option is separate.

The optical group is a child of its host and follows that carrier's motion.
`CarrierHostName` records this parent; `MountSide` selects the ±X edge.
Reattaching uses `optical_interface.attach_to_host`. Slot compatibility does not
mean every populated host, edge or optional power arrangement clears the sensor,
its connector and field of view. Follow the composed configuration checks; an
occupied FC carrier is not automatically an acceptable optical host.

The two separated screws resist in-plane rotation after tightening. Their
clearance and the slot permit alignment during assembly, not free movement in
operation. Seat the foot flat, tighten without crushing PA12 and check pointing
retention/creep. Disconnect wiring before removal. The one pitch axis does not
correct roll or automatically level the sensor.

## Balanced output supports and replacement space

| Nominal dimension | BH | BI |
| --- | ---: | ---: |
| Bearing centre spacing per rotor | 75.5 mm | 70 mm |
| Gear tooth centre to nearest bearing centre | 8.25 mm | 11 mm |
| Shaft grip length | 13.5 mm | 10 mm |
| Straight support-post depth | 6 mm | 6 mm |
| Driven / idler / input rod lengths | 34 / 22 / 18 mm | 34 / 20 / 18 mm |
| Present 40 mm propeller guard OD / ID | 48.6 / 45.6 mm | 50 / 46 mm |
| Initial shaft retraction for rotor removal | 14.5 mm | 12 mm |

Two bearings support each complete rotating carrier, but each shaft is a separate
stub joined through PA12; this is not one continuous steel shaft. Moving the
bearing farther from the gear increases the tooth-force bending moment: the
11/8.25 ratio is approximately 1.33. The compromise restores service room while
retaining longer grips and thicker posts than the earlier BG design. Geometry
alone does not prove acceptable loaded mesh deflection, wobble or life.

Four existing 3×6×2.5 mm bearings, their integral outer-ring capture and independent
carrier axial stops remain. No purchased spacers, extra bearings or caps are
added. The existing Ø3 rod remains nominal; actual diameter, straightness, bearing
clearance and printed clamp fit require checking. Use a matching precision rod
if delivered stock does not fit.

Both sides reserve a future replacement rotor bulk within local |Y| ≤30 mm and
rotation radius 34 mm. The enclosing cylinder covers all tilt angles and includes
nominal ±0.5 mm axial travel. Each inner support face has 1.75 mm nominal clearance
to that bulk, falling to 1.25 mm at its axial stop. Checks include retained physical
propulsion parts, rotor removal in +X and reciprocal servo-module removal.

This is a space allowance for designing a future 50 mm propeller carrier. The
present Ø46 mm guard opening and struts do **not** accept a 50 mm propeller.
A future carrier must retain suitable shaft/clamp interfaces and revalidate its
motor, hub, guard, wiring, load and motion. Current carrier/frame stop clearance
remains 0.5 mm per side; do not remove those stops to create bulk clearance.

## Dimension cleanup

Meaningful CAD values are now 150/50 mm main-axis datums, 70 mm bearing span,
10 mm grips, 20 mm idler rods, 50/46 mm guard and 35 mm optical pivot height.
The 340 mm rail and the carrier's 64 × 64 mm deck with 2 mm thickness remain;
the integral carrier's overall height is 13.2 mm. Standard interfaces remain.

Preserve derived quarter-millimetre bearing/stop locations, the 2.5 mm bearing
width, OEM horn geometry, FC 25.5 mm pattern and P-AS offsets. Carrier seat/nut
heights preserve screw-tip clearance and cannot be rounded independently.
Dimensions whose fit function matters are not cosmetic rounding candidates.

## Quotation and evidence

Export unique manufacturing-local print geometry, with explicit quantities:
eight baseline print types/twelve pieces, three separate fit coupons, and the
optional power platform separately. STL and STEP are alternatives for the same
parts; they must not be counted twice. Purchased parts and device envelopes are
excluded. Downloads files are quotation artifacts, not a supplier-approved order.

Creallo accepts STEP/STL with quantities; its quote upload guide specifies a
50 MB per-file limit. PA12 remains the material basis, with SLS/MJF, grade, finish
and one-piece acceptance to be agreed. Its published maximum fabrication sizes
include joined parts and do not establish one-piece acceptance of the rail.
Use matching process/material/finish/orientation for fit coupons and full parts.
[Quote guide](https://creallo.com/en/doc/how-to-use-creallo-realtime-quote),
[process](https://creallo.com/ko/capability/process/3DP/SLS),
[design limits](https://creallo.com/ko/guide/design-spec-guide).

[Verification manifest](bi_design_verification.json) records exact source, native
CAD, tests and exported files. Passing geometry checks does not qualify physical
fit, strength, retention/creep, harness motion or flight.
