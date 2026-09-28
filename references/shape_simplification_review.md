# Printed shape and support review — AO

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

The AL roll bracket widens its connecting post from 2 by 2 to 3 by 2 mm.
The wider straight post begins 2.8 mm above the roll axis, inside the first
ear's outline, and stays in the pitch ear's plane. This preserves all prior
material while increasing the section between the two ears without a new
rib, part or fastener. The pivot axes, clamping faces, screw lengths, sensor
height and adjustment range are unchanged. Extending the post behind the
pitch ear would obstruct its screw head and is deliberately avoided.

The added material stays at least 0.4906 mm outside the modeled roll nut's
full rotational envelope and 1.25 mm from the pitch screw head. These are
nominal CAD margins, not guaranteed delivered clearances or tool-access
allowances. Confirm the actual nut, screw head and print. The provisional PA12 mass increase is about 0.01 g. Section enlargement
is intended to reduce local bending; no measured stiffness or pointing
accuracy is claimed.

## Central paired servo module

The central paired servo/input-drive arrangement introduced in AJ remains. Its
cradles merge into one continuous upright with two 8 by 21 mm case windows,
3 mm outside walls and a 4.8 mm central web. The bought servo ears still locate
and clamp each case; the case windows are clearance features, not press fits.
Allowing the manufacturer's case-size tolerance of ±0.2 mm and a printed-window
size allowance of ±0.3 mm leaves 0.5 mm minimum total size-only clearance in
each window direction. AS restores solid 3 mm outside walls: the purchased
horn's front screws no longer need rear tool reliefs. Preserve the ordered
module removal and bench service path from [the retention review](retention_review.md).
Actual positions, flatness and lead exit still need inspection.

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

Keep the selected gear bodies, shaft journals and mesh geometry source-specific.
Bearing outer-ring contacts and shield clearances need the actual lot and
production-matched retention coupon; do not restore separate spacer lands.
Gear axial positioning uses their existing shaft/set-screw interfaces; do not squeeze unknown hub thicknesses between new printed walls.
The input metal stubs retain their full-length flat and prescribed socket
engagement. The selected 8 mm gear body leaves 2 mm of shaft beyond its outer
face. This gives small axial fitting freedom without
new printed walls or fasteners; the opposite gear face overlap and actual M3
set-screw position still limit usable adjustment. A different gear thickness
requires measured engagement and renewed collision checks, not an assumption
of universal compatibility. Finish the input D socket against the actual stub.
The AS purchased-horn adapter has an open root saddle and factory-hole
round/slot allowance; actual fit and runout checks remain required in
[the retention review](retention_review.md). Device holes and optical foot holes
retain assembly clearance for relative hole-position errors; their tightened
face contacts, rather than loose-hole diameters, provide the operating seat.
Connector reserves, optical visibility and moving-part separation are not
unnecessary play and must not be reduced to achieve a snug mechanical fit.

## AS purchased-horn adapter

The [selected 15T/4.0 mm horn](retention_review.md#selected-replacement-horn--2026-09-25)
uses two factory M1.6 threads. One printed adapter supplies an open root saddle,
flat seat and round/short-slot clearance. Both screws enter from the gear side;
there is no rear cap, enclosing arm shell, horn attachment nut or centring jig.

The selected first/third hole spacing accommodates the accepted screw heads;
the outer slot tolerates the inferred third position. Adjustment occurs before
tightening, not through an intentionally loose running joint. Root and axial
fit remain prototype assumptions, not certified purchased dimensions.

The servo bridge's former rear screwdriver scallops are filled because these
screws now withdraw forward. Its side columns become simpler and continuous.
The source service checks first remove the paired module, then withdraw the
input gear on the bench before front screw access. Keep the paired servo/input-drive module separable from the output frame.
