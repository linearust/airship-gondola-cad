# Selected drivetrain and preparation contract

Selected purchased interfaces are recorded in the [final cart snapshot](cart_selected_parts_2026-09-29.json). Nominal selection does not establish received fit, strength or loaded performance.

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
  The [horn contract](../gondola/contracts/servo_horns.py) selects manufacturer
  X06 stock plastic half arm 1 on both sides. Preserve its nominal STEP geometry
  except the two existing Ø1 mm holes at 6.8/13.2 mm, enlarged to Ø1.5 mm for
  rear M1.4×8 screws and front M1.4 nuts. The common printed adapter uses an
  open Ø7.3 mm root seat, a near Ø1.8 mm round hole and a far 1.8 × 2.4 mm
  radial slot. Centre the axes before tightening both attachments; the slot
  accommodates assembly pitch error, not operating slip or shaft eccentricity.
  Follow the preparation and ordered service sequence in
  [OEM horn compatibility](servo_horn_compatibility.md). Delivered
  fit, prepared-horn strength, runout and loaded retention remain unverified.
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

The stock-preparation keys encode cut length and optional local-flat length and
offset. Flat depth is nominally 0.5 mm. Cut square, deburr and keep all output
bearing journals round. The input stub may have a full-length flat because it
has no external bearing journal. Flats and gear set screws must be clocked to
one another; do not infer tooth-to-screw phase from the seller images.

The user confirms the four [generic 3 x 6 x 2.5 mm bearings](https://www.aliexpress.com/item/1005007668446060.html)
from the original final cart were purchased and must remain in this iteration.
They are not identified as NSK/ISC parts. Retained ISC MR63ZZ data remain a
comparison, not certification of the received lot or its mass. The design uses fixed
round seats, integral rear shoulders and four identical keyed front keepers,
each fixed by one ordinary M2×6 screw/nut pair. Keepers seat on the frame,
without intended bearing preload; no radial clamp or purchased bearing spacer
is used. Shaft grip and nominal ±0.5 mm carrier stops remain independent.
Qualify the production cup/keeper coupons, actual ring lands, shield clearance,
radial fit and removal paths as described in the [current retention review](bearing_keeper_review.md).

## Release and physical verification

The source selection describes the intended build. Native CAD, exported parts,
procurement, motion/service checks and the pinned fixture must be regenerated
and independently reviewed together before a release represents this selection.
Older clearance reports and mass totals do not qualify a changed source or CAD.
Geometry checks do not establish actual fit, screw retention,
PA12 creep, actuator load capability or flight readiness.
