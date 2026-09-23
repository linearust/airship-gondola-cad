# Printed shape and support review — AK

The design preference is simple, integrated, inspectable geometry. A modest
mass increase is accepted where it removes narrow branches or complicated
local reliefs. Broader sections are geometric improvements, not a measured
strength, stiffness, fatigue or PA12 creep rating.

## Optical base

The former top beam extended 6.7 mm beyond each leg because its length reused
the outboard foot allowance. Those two top overhangs served no attachment or
optical function. The beam now ends flush with the legs, forming a plain open
portal. Its section is 3 by 8 mm; the legs are 2 by 8 mm. The full roll-pivot
root is supported without a separate tab or gusset.

The host deck and feet remain 2 mm thick. Host seats, mounting hardware,
sensor height, pivot axes and manual angle limits are unchanged. Changing the
beam thickness must not change the shared host-deck thickness or move the
optical axes. Both hosts still require optical, connector, registration and
complete-tower service checks.

## Central paired servo module

AJ moved the two servo/input-drive assemblies 23.5 mm inward on each side; AK retains those positions. Their
cradles merge into one continuous upright with two 8 by 21 mm case windows,
3 mm outside walls and a 4.8 mm central web. The bought servo ears still locate
and clamp each case; the case windows are clearance features, not press fits.
Allowing the manufacturer's case-size tolerance of ±0.2 mm and a printed-window
size allowance of ±0.3 mm leaves 0.5 mm minimum total size-only clearance in
each window direction. Actual positions, flatness and lead exit still need
inspection.

The common upright stands on a 26.8 by 22 by 2 mm central plate. Two broad
15.6 by 18 by 2 mm straight arms join the diagonally opposed mounting feet
with 3 mm overlap onto that plate. Removing the unused side regions opens
the view to the frame without enclosed windows or a thin perimeter. The
frame's solid shoe roof directly contacts the central plate underside, so
the servo loads do not depend solely on bending between the outer feet. The original two M2 mount pairs, open head-access bores and fixed X/Y
datums remain. The two outer seats at Z8.7 must be coplanar with each other;
the higher central seat at Z11.4 must simultaneously contact its matching
underside. Reject rocking rather than drawing a warped plate down with the screws. The complete paired
servo/input-drive module stays removable from the output-bearing frame.

The AJ propulsor centre-spacing change from 178 to 131 mm is retained. This shortens the bearing
support arms and narrows the assembly. For the same differential thrust and
unchanged geometry otherwise, the corresponding moment arm is 26.4% smaller.
This is a control-authority trade-off, not an aerodynamic efficiency gain.
Update vehicle actuator geometry/control allocation before flight; this CAD
change does not qualify the controller or actual flight response.

The [KST X06 V6 drawing](kst_x06_v6_datasheet.pdf) defines the nominal case
and ear geometry, but does not dimension a finished lead/connector envelope.
The plate leaves 5.136 mm below the nominal case body; the lower mounting ear
is a different surface and is not a wire corridor. Keep the rear-case planning
spaces clear through the complete bounded input rotation. These are design
allowances, not certified lead exits, bend radii or connector specifications.

## Propulsor support floor

The former long perimeter openings are filled by plain 18 mm wide, 3 mm thick
integral feet. Narrow parallel strips and small transverse foot additions are
unnecessary. The short central floor remains 2 mm thick to preserve the rail
clamp's key/head access; no holes pierce the bearing-post roots. The central
servo seat directly transfers the common upright load into the rail shoe.

[Creallo's guide](https://creallo.com/ko/guide/design-spec-guide), checked
2026-09-23, lists 2 mm for 150 mm and 3 mm for 200 mm-plus thin/broad SLS PA12
structures. The approximately 197 mm frame uses the more conservative 3 mm
outboard floor while SLS/MJF selection is pending. This is a manufacturing
and geometric design choice, not a measured strength, stiffness or fatigue
qualification.

## Fit priorities

The T-head is a matched close-running interface; its width and height have
separate fit allowances and the web remains relieved. Follow
[the rail fit review](rail_fit_review.md) and trial the actual coupons before
ordering complete carriers. A small nominal clearance is not an as-printed
fit guarantee or a prediction of insertion/holding force.

Keep the selected gear bodies, shaft journals, spacer lands and mesh geometry
source-specific. Gear axial positioning uses their existing shaft/set-screw
interfaces; do not squeeze unknown hub thicknesses between new printed walls.
The input metal stubs increase from 16 to 18 mm, retaining their full-length
flat and 8 mm socket engagement. The selected 8 mm gear body leaves 2 mm of
shaft beyond its outer face. This gives small axial fitting freedom without
new printed walls or fasteners; the opposite gear face overlap and actual M3
set-screw position still limit usable adjustment. A different gear thickness
requires measured engagement and renewed collision checks, not an assumption
of universal compatibility. The horn register and input D socket retain
0.05 mm nominal finish-fit allowances and still require fitting. Device holes and optical foot holes
retain assembly clearance for relative hole-position errors; their tightened
face contacts, rather than loose-hole diameters, provide the operating seat.
Connector reserves, optical visibility and moving-part separation are not
unnecessary play and must not be reduced to achieve a snug mechanical fit.

## Open horn adapter

Both long walls around the horn blade are removed. A constant-thickness semicircular root
register and a central tip stop, 3 mm wide by 1.8 mm thick, retain nominal
location with the existing 0.05 mm finish-fit allowance. Removing every
locating surface would make shaft centring depend on loose bolt holes. The
broad front face and existing M1.6 through-bolt still clamp the blade. The
remaining locating faces alone are not a torque-retention qualification.

The adapter still installs axially over the already retained OEM horn. The
socket floor, original-screw cavity, metal shaft and radial M2 nut housing
are unchanged. Saved-geometry checks verify that small local X/Z translations
encounter the locating faces on both sides through representative attitudes;
these rigid checks do not predict combined fit errors, preload or creep.

## Straight P-AS support

One straight 5 by 2 mm arm now runs from the central rail shoe at (0, -9.3)
to the existing P-AS holes at (42.5, -9.3) and (65.5, -9.3) mm in the mount
frame. It replaces the former diagonal branch from the FC support. All device
hole centres, support heights and wire reservations remain unchanged. This
simplifies the load path and outline; actual loaded deflection remains
unmeasured.

## Other reviewed features

The horn adapter retains its prepared metal stub and admits the radial nut. The motor-carrier split slots provide shaft
clamping; its end flanges and the frame shoulders retain the bearing stack.
Those features remain functional. Filling them would obstruct assembly or
remove retention, rather than simplify an equivalent assembly.

The continuous bearing-post roots and solid rail clamping head from AH remain.
Device supports retain verified mounting axes and the existing connector
reservations. No new fastener family or printed separation is introduced.
