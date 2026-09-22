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
  Retain the selected KST 0415.13 horn and design its coupling around a short
  nominal-3mm input stub. Do not shrink the former hollow Ø7 coupling post.
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

Use the user's selected [6061 nominal Ø3 x 330 mm rod](https://www.aliexpress.com/item/1005005983061241.html),
cut to CAD lengths. This supersedes finished MISUMI PSFU3 orders. The diameter,
roundness, straightness and alloy temper are unspecified. Measure actual
bearing/gear fits before preparing the entire batch. If unsuitable, use a
measured precision nominal-3mm replacement rod while preserving the interfaces.

The stock-preparation keys encode cut length and optional local-flat length and
offset. Flat depth is nominally 0.5 mm. Cut square, deburr and keep all output
bearing journals round. The input stub may have a full-length flat because it
has no external bearing journal. Flats and gear set screws must be clocked to
one another; do not infer tooth-to-screw phase from the seller images.

The selected [generic 3 x 6 x 2.5 mm bearings](https://www.aliexpress.com/item/1005007668446060.html)
are not identified as NSK/ISC parts. Retained ISC MR63ZZ data remain a dimensional
comparison for the shoulder/cap design, not certification of the selected lot
or its mass. Verify race-land and shield clearance, shaft fit and axial capture.

## Release and physical verification

The source selection describes the intended build. Native CAD, exported parts,
procurement, motion/service checks and the pinned fixture must be regenerated
and independently reviewed together before a release represents this selection.
Previous revision-AA clearance reports and mass totals do not qualify this
conversion. Geometry checks do not establish actual fit, screw retention,
PA12 creep, actuator load capability or flight readiness.
