# Selected drivetrain and preparation contract

The user's latest cart-based selection supersedes the previous MISUMI-only
purchasing request and the former 60T/20T and 64T/20T CAD configurations.
Existing geometry is not a constraint. Optimize the complete indoor LTA
mechanism, including couplings, retention, printability and replacement access.

## Selected configuration

`gondola/contracts/drive.py::SELECTED_DRIVE` selects **48T driver / 16T output**,
module 0.5, pressure angle 20°, with **nominal Ø3 mm plain bores in both gears**.
The selected Kailash Store options and per-gear dimensions are recorded in
[the retained seller evidence](kailash_gears_selected_evidence.md). The thinner
48T driver and thicker 16T output must each use their own axial dimensions.
Their source selection is not an assertion about physical fit or strength.

- External mesh reverses rotation: nominal ±60° input gives ±180° output.
  A servo reaching only ±59° would still produce only ±177° output.
- Reference centre distance is 16 mm. Printed axis positions, actual backlash,
  free rotation and output loading require checks with the received gears.
- Both bores remain 3 mm; neither is a directly compatible X06 spline.
  The current [horn contract](../gondola/contracts/servo_horns.py) supports all
  three retained 4 mm/15T horn drawings independently on either side. Its
  selected mixed pair is `PTK_6_6` on Port and `METAL_6_98` on Starboard; KST
  0415.13 remains a supported alternative. The user's accepted X06 compatibility
  premise does not establish received-part fit.
  One shared [printed adapter](../gondola/parts/servo_coupling.py) uses an open
  root seat and one continuous radial slot. Both threaded metal profiles use
  their first and third existing M1.6 threads with two front M1.6×5 screws,
  without horn drilling or attachment nuts. KST requires enlarging only its
  existing end pilot holes at 4.5 and 13.2 mm to Ø1.5 mm, then using rear M1.4×6
  screws and front M1.4 nuts; its factory holes are plain, not M1.6 threads.
  Follow the profile-specific head/nut limits and assembly/service order in
  [three-horn compatibility](servo_horn_compatibility.md). The nominal-3mm input
  stub and gear axial plane are retained. Centre the axes before clamping both
  attachment points; the slot permits assembly adjustment, not running slip.
  Actual axial seating, root fit, concentricity and loaded retention remain
  unverified. The former AS round-hole/outer-slot and M1.6×4 instructions are
  superseded.
- The user deferred the 48T material-description conflict and gear masses.
  Keep these uncertainties in accounting without blocking the authorized
  dimensional design; do not report POM materials or assert weight reduction.
- The M3 radial gear screws will be selected later. The 16T screw axis is
  dimensioned; the 48T position, actual screw length and point are not.
  Preserve those limits in CAD access checks and the purchase list.
- The paired servo bridge remains removable from the common output-bearing
  frame. Ratio changes are complete mechanism changes requiring new sourced
  parts, geometry and validation; no alternate ratio is currently supported.

## Rod and bearing selection

Use the user's selected nominal Ø3 mm 304 rod. Input-stub length and flat depth
are owned by [servo_coupling.py](../gondola/parts/servo_coupling.py)
(`SHAFT_LENGTH`, `SHAFT_FLAT_DEPTH`); output-shaft geometry and preparation keys
are in [propulsion.py](../gondola/parts/propulsion.py). Match these to the
[installed inventory](../gondola/contracts/design.py) and generated hardware BOM
before cutting. The seller's material description does not establish diameter
tolerance, roundness or straightness. Measure bearing/gear fits before preparing
the entire batch.
If unsuitable, use a dimensionally verified nominal-3mm precision replacement
and recheck grip and fit. Current preparation is summarized in
[the cart review](cart_adaptation_review.md).

Historical choices only: finished MISUMI PSFU3 and the earlier
[6061 rod listing](https://www.aliexpress.com/item/1005005983061241.html) are
superseded. Retaining their evidence is not an instruction to order them.

The stock-preparation keys encode cut length and optional local-flat length and
offset. Flat depth is nominally 0.5 mm. Cut square, deburr and keep all output
bearing journals round. The input stub may have a full-length flat because it
has no external bearing journal. Flats and gear set screws must be clocked to
one another; do not infer tooth-to-screw phase from the seller images.

The selected [generic 3 x 6 x 2.5 mm bearings](https://www.aliexpress.com/item/1005007668446060.html)
are not identified as NSK/ISC parts. Retained ISC MR63ZZ data remain a dimensional
comparison only, not certification of the selected lot or its mass. The frame
now captures each outer ring with an integral shoulder and two releasable hooks;
there are no purchased bearing spacers or separate caps. Shaft grip and the
carrier/frame axial stops remain independent. Qualify the matching process
coupon, actual ring lands, shield clearance and release path as described in
[the retention review](retention_review.md).

## Release and physical verification

The source selection describes the intended build. Native CAD, exported parts,
procurement, motion/service checks and the pinned fixture must be regenerated
and independently reviewed together before a release represents this selection.
Older clearance reports and mass totals do not qualify a changed source or CAD.
Geometry checks do not establish actual fit, screw retention,
PA12 creep, actuator load capability or flight readiness.
