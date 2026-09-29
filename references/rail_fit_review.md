# Rail matched fit and attachment

Scope: the one-piece T rail and integral carrier/frame shoes. Keep
the removable paired servo/gear module separate. No purchased gear, bearing,
shaft or servo-fit allowance is tightened by this rail-interface change.

## Geometry

`gondola/parts/rail.py:fit_contract()` is the numerical source of truth. The
10 × 3 mm rail head runs in a nominal 10.2 × 3.2 mm channel: total
lateral and vertical clearance is 0.2 mm. The recessed web
retains 0.45 mm per-side relief, so it does not compete with the head datum.
The basic 18 × 22 mm shoe retains Z2.2–10.8; the propulsion frame alone
extends its solid roof to Z11.4 to support the central servo plate.

Two 0.3 mm, 45° entrance chamfers leave a 17.4 mm straight running section.
The straight-section head roof is 2.3 mm and lower jaw 3.1 mm; their
entrance minima after chamfering are 2.0 and 2.8 mm. The minimum entrance-to-nut
wall is 1.55 mm and nut-port roof 1.825 mm. No spring, sacrificial rib, liner or
additional hardware is introduced. The existing M2x8 screw and hex nut are
an additional lock; their seated module shift follows the 0.1 mm side gap.

The Ø2 mm screw face retains 0.5 mm upper/lower margins on the solid head.
Nominal opposing jaw contact is 34.3425 mm² at a land centre and 32.5725 mm²
at either allowed ±4 mm offset after the entrance bevels. These are contact
geometry measurements, not load, indentation, friction or creep ratings.

## Repeated attachment wings

The user's fabrication review requires a nominal minimum 1.5 mm tape-attachment
thickness. Both the one-piece rail base and every tape wing now use 1.5 mm;
the 340 mm length, head, shoe and all equipment/propulsor datums stay unchanged.

Ten identical rounded 14 × 32 mm wing pairs repeat at 36 mm pitch, centred at
X −162, −126, −90, −54, −18, +18, +54, +90, +126 and +162 mm. Both ends and
both sides are symmetric. Every wing centre meets a full head land. Adjacent
wing footprints leave the same 22 mm longitudinal gap; no extra local wings
or thin adhesive ledges are used. The existing 12 mm-wide tape references
are raised with the wings, leaving 0.55 mm nominal clearance below the shoe.

The propulsion shoe at X0 is bracketed by the wings at X±18. Its 18 mm
footprint ends 2 mm from their inner edges. Battery X90 and FC X−54 retain
centred tape support; navigation X−158 stays 4 mm from the end wing centre
and within that 12 mm tape reference. This is support proximity, not a
strength or adhesion qualification. A wing on every 18 mm head land would
add avoidable material and tape application work; the uniform 36 mm pattern
retains nearby support without that duplication.

The thicker base increases bending stiffness; the unchanged 4.5 mm head/web
reliefs and 0.5 mm roots do not guarantee the previous curvature response.
Print the updated rail coupon, then test the full rail at the actual envelope
curvature and loading. Nominal 1.5 mm geometry is not a delivered-thickness,
fatigue or minimum-bend-radius guarantee.

## Manufacture and acceptance

[Creallo's current specification guide](https://creallo.com/ko/guide/design-spec-guide)
lists SLS/MJF dimensional tolerance ±0.3%, minimum ±0.3 mm; its general assembly
guidance uses a 0.3 mm gap. This closer 0.2 mm nominal trial is deliberately
conditional on matching coupons, not a guaranteed as-printed fit. Applying two
independent ±0.3 mm size errors alone gives a raw gap range of −0.4 to +0.8 mm
in either head dimension. Surface texture, curvature and straightness add
further uncertainty; no nominal interference or insertion force is prescribed.

Print the existing rail/shoe coupons using the agreed PA12 process, finish and
corresponding production feature orientation. With the clamp screw backed off,
the pair must slide with deliberate hand pressure without perceptible rocking
or free sliding. Lightly finish tight head-contact faces evenly. A loose pair
requires dimensional compensation and another coupon; sanding cannot reduce
clearance. Do not force or distort the flexible rail to obtain assembly.

After accepting coupons, check every final carrier on the full rail throughout
its intended straight and installed curved travel. A short coupon cannot
qualify full-length straightness, curvature, friction, wear or holding force.
Only then use hand-snug clamp pressure and check indentation, creep and loaded
retention. Maintain open flex gaps and tape-free running surfaces.

## Checks

Native geometry checks reject the former loose channel and an undersized
channel: ±0.1 mm Y/Z movement reaches the nominal boundary without overlap,
while an additional 0.02 mm intersects the capture faces. These checks do not
simulate friction or prove the required physical hand fit. Rail reliefs remain
open through the full head height; full-tip/opposed-jaw load-path checks remain.
Assembly seating, preview offsets and release-to-centre paths derive from the
same side gap. Native rail, module and coupon annotations share `fit_contract()`.
