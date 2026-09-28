# BD rail and mounting review

Keep the existing flexible tape-mounted rail and three identical square carriers.
Two local changes improve the nominal load route without adding printed parts or
fastener varieties. The paired servo/input module remains detachable. Dimensions,
clearances and calculated masses below are CAD values, not physical qualification.

## Integral carrier support

Replace the 12 × 12 mm post between each rail shoe and deck with one solid Ø17 mm
circular support. Its exposed height remains 2.6 mm; the plate, device/stack slots,
shoe, clamp and equipment placements are unchanged. The circle contains the old
square and increases support section area from 144 to 226.98 mm². This is not a
whole-carrier stiffness or strength multiplier: deck bending, clamp compliance,
print properties and installed loads remain unmeasured.

The wider support retains the continuous underside paths for the conservative
Ø4.5 mm M2 head envelope. The minimum nominal head clearance is 0.564 mm; both
nut insertion routes, screw release and the complete existing L-key approach
remain clear. Each carrier adds 215.748 mm³ (about 0.218 g using the provisional
1.01 g/cm³ PA12 density). No separate spacer, rib or additional fastener is needed.

A larger Ø17.5/18 mm circle reduces the minimum head clearance to 0.314/0.064 mm,
below the existing 0.4 mm design allowance. A full rectangular support collides
with slot-head paths; cutting clearance channels adds complexity. Retain Ø17 mm.

## Tape support at the battery station

Keep the seven former wing stations and add a pair of lateral wings at each of
X−90 and X+90 mm. The resulting nine stations are symmetric:
−162, −108, −90, −54, 0, 54, 90, 108 and 162 mm. Each station has two independent
tape-strip references, one per side. The rail remains one printed part, with its
340 mm length, uninterrupted base, T-head, flex reliefs and close shoe fit unchanged.
The 48 mm single-station coupon geometry is also unchanged.

The default battery carrier at X+90 now sits over the same head land as a tape
wing, instead of transferring its nominal load toward the X+108 wing across the
intervening relief. Adding symmetric wings costs 855.058 mm³ (about 0.864 g).
Moving the old ±108 wings inward would save this addition but increase the largest
wing spacing from 54 to 72 mm and reduce support choices for later CG trim.
Retaining both is a small mass tradeoff consistent with the user's priorities.

Together the rail and three carriers add about **1.517 g of modeled PA12**. The
extra tape mass is unknown and excluded. This is not a measured assembly mass.
The actual saved module/tape placements now appear in the rail validation report;
their proximity does not prove tape adhesion, bending strength or holding force,
and other trim positions are not prohibited. Recheck support and wires after trim.

## Retained limits and alternatives

- Keep the secondary M2 lock on a full head land. A screw over a flex gap can
  advance until its head bottoms against the shoe wall, producing a false impression
  of clamping.
  The existing recommended stations keep the tip supported; arbitrary rail
  coordinates do not. Do not cure this with excessive tightening.
- The close straight shoe/rail gap does not establish curved installed fit. A
  simplified rigid-land curvature probe found interference or nearly exhausted
  clearance at some radii/positions. It omits elastic deformation, actual tape and
  surface shape; it establishes no minimum bend radius. Test matched coupons
  straight and at the intended curvature, then the full taped rail at all used
  stations. Do not widen the whole channel merely to hide this uncertainty.
- A pressure tongue, snap clamp or middle-of-rail lift-off interface would add
  flexure/creep and retention questions. The current end-loaded shoe is retained;
  no unqualified new latch is introduced just to remove an M2 pair.
- No reduction in the general print-fit allowance is claimed. PA12 finish,
  installed curvature, clamping/creep, adhesive area/contact and real load tests
  remain necessary before fabrication or flight readiness claims.

## Export precision

The new rail exposed an STL precision issue: after native save/reopen, equivalent
face triangulations at a corner-based origin differed by 0.000010789 mm, just
above the existing 0.00001 mm surface-identity limit. The checker correctly
rejected them. Centre each export's exact XY bounds before meshing to reduce
float32 rounding; retain the print rotation and Z=0. Compensate the overview's
translation to preserve its positive, separated layout. Installed geometry,
native corner-origin `PrintPlacement` metadata, mesh settings and comparison
tolerance are unchanged. This improves numerical precision, not print accuracy;
arbitrary future shapes still need the same strict export checks.

Retain the actual opposite-diagonal counterexample as a rejecting regression,
plus native round-trip and origin/layout checks. The initial failed export run is
historical diagnostic evidence, not acceptance of the final source.

Independent old/new native geometry, controls and metadata review precedes fixture
promotion. Final exact-source tests, saved-CAD checks and rendered inspection are
recorded in `bd_rail_mount_verification.json`; detailed evidence is retained in Git.
