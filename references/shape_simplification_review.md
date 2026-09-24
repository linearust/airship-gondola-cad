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
each window direction. The outside walls include open-edge access reliefs for
the prepared horn fasteners; the nominal 3 mm wall does not describe the
minimum at those local reliefs. Keep the checked example fastener locations
and ordered service path from [the retention review](retention_review.md).
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
The supplied horn has no assumed outline-fitting register; its prepared
adapter and temporary jig require the actual fit and runout checks in
[the retention review](retention_review.md). Device holes and optical foot holes
retain assembly clearance for relative hole-position errors; their tightened
face contacts, rather than loose-hole diameters, provide the operating seat.
Connector reserves, optical visibility and moving-part separation are not
unnecessary play and must not be reduced to achieve a snug mechanical fit.

## Supplied-horn adapter

AM replaces the earlier purchased-horn root register, tip stop and single
through-bolt layout. The current printed part is a plain machining blank
without assumed horn attachment holes. Its illustrative prepared assembly and
the temporary bench jig are distinct from the exported blank. Preserve the
socket floor, gear datum and material needed for the actual two fastening
sites; do not restore the former horn-outline-fitting surfaces.

Preparation and service belong to [the retention review](retention_review.md)
and `parts/servo_coupling.py:machining_contract()`. The small jig, hole fits and
nominal CAD example do not establish concentricity or loaded retention for the
unmeasured supplied horn. Other prepared hole locations require renewed
clearance and tool/removal-path checks.

## Shared equipment support

The electronics carrier uses two straight, continuous 5 by 2 mm members.
The X member supports the FC mounting pads and extends through both P-AS
mounting pads; the Y member supports the other FC pads and the LR900-A adhesive
deck. This removes the P-AS arm that previously ran parallel to the FC arm at
Y=-9.3 mm. The small round ends of separate collinear arm primitives are also
unnecessary in the generator; each shared member is built once.

The P-AS centre moves from (54, 0) to (54, 9.3) mm in the electronics carrier
frame so its published off-centre hole row lies on Y=0. The complete device
and its connector reservation move together. Its two holes remain 23 mm apart
at X=42.5 and X=65.5; device orientation, support elevation and 6.5 mm mounting
pads are retained. The FC axes and LR900-A location do not change. Do not
move P-AS closer to the FC: its current X position preserves the existing
connector-handling allowance.

The provisional capacitor reservation moves from (40, 22) to (42, 34) mm,
retaining its diameter 10 mm, height 16 mm and Z elevation. Simply moving it
to (40, 32) would clear installed parts but obstruct optical foot-nut removal.
The selected location also preserves the checked tool and tower-removal paths.
This is reserved space, not a new capacitor mount or verified antenna/lead
installation.

The optical diagonal supports carry the transferable tower independently of
the FC dampers and do not duplicate either equipment member. Keep their broad
seats and the battery's continuous adhesive contact area. The shared spine
removes a redundant branch without thinner walls, a new joint or more
fasteners. Actual loaded deflection and mounting-stack fit remain unmeasured.

## Other reviewed features

The horn adapter retains its prepared metal stub and admits the radial nut.
Motor-carrier split slots grip the shafts; carrier end flanges and frame stops
limit rotor travel. Separate integral frame hooks and shoulders retain the
bearing outer rings. These are distinct retention paths, described in
[the retention review](retention_review.md), and remain functional. Filling them
would obstruct assembly or remove retention, rather than simplify an equivalent
assembly.

The continuous bearing-post roots and solid rail clamping head from AH remain.
Device supports retain verified device-local hole patterns and full connector
access allowances. No new fastener family or printed separation is introduced.
