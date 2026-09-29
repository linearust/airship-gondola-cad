# Centreline optical support

BF design review, 2026-09-29. The sensor moves onto nominal carrier Y=0 while
retaining the original two clamps in the corner slot at carrier X=27 mm,
Y=13 and 23 mm. One low, integral L arm joins that foot to the outboard upright.
There are still two printed parts and three ordinary M2×8 screw/M2 nut pairs:
two for the foot and one for manual pitch. No locator, extra mounting hole,
intermediate bracket or new fastener is introduced.

A foot centred on the new side-midpoint slot would intrude into the FC's existing
underbody wiring corridor. A nearby upright would also cross its peripheral
connector band. Keeping the corner foot and moving the upright outboard clears
those reservations without shortening or narrowing them. The larger cantilever
and footprint are deliberate costs of centring the sensor while preserving both
battery and FC host options.

## Geometry and assembly

Dimensions are nominal millimetres. Pedestal coordinates start at carrier
(27,18,15.4); the carrier support face and foot interface are unchanged.

| Feature | Current geometry |
| --- | --- |
| Foot | 8 × 16 × 2, centred at pedestal X=−1; two Ø2.6 bores at (0,±5) |
| Low arm | Two straight integral beams: outboard 5 × 3 section, return 6 × 3 section |
| Upright | 6 × 2 section; low triangular buttress extends 2 in +Y, ending at Z=10 |
| Pitch pivot | Pedestal (23,−18,22), hence carrier (50,0,37.4) |
| Both pitch ears | Ø8 × 2, with Ø2.6 clearance bores; radial wall 2.7 |
| Sensor tray | Existing 18 × 12 adhesive deck; 2 thick with 1 adhesive allowance |
| Base envelope | 32 × 28 × 26, previously 10.5 × 16 × 25.5 |

The larger ear leaves a nominal 0.5 mm gap to the tray underside, previously
1 mm. The sampled assembled pitch range remains ±20° with no modeled collision;
actual printed clearance and hardware fit still require inspection. Both ears
remain 2 mm thick, preserving full nominal 1.6 mm nut engagement and 2.4 mm screw
tip projection. The foot's existing 4 mm total grip is unchanged.

The nominal pivot is on each host's carrier centreline, not a claim of zero
installed world-Y error. The common rail shoe retains its nominal ±0.1 mm lateral
clearance, and the two slot-end clamps retain their bounded XY/yaw assembly
allowance. Tighten and align the module before use; these allowances are not an
operating adjustment or a qualified pointing tolerance.

Disconnect the sensor and bench-support the removed carrier. Hold the foot nuts
while withdrawing both screws downward. Slide each freed nut 12 mm outboard
along carrier +X, then lift it 40 mm along +Z. The shorter nut slide avoids the L
return arm. Then slide the complete pedestal 20 mm +X and lift 40 mm +Z. Direct
vertical pedestal removal is not specified because it crosses the FC connector
band. Installed cables and the balloon are outside this service model.

## Evidence and limits

A focused native probe rebuilt the current optical kit and all three current
carrier shapes in memory, using the existing saved assembly and unchanged wiring
reservations. Both MTF02P and MTF01P passed the complete optical host checks on
both battery and FC carriers: sampled pitch, continuous external field,
registration bounds, attachment, tool access and ordered removal paths. The
five separate base bounds contain the actual solid and leave the L interior
open. Their minimum FC-wiring gap is 2.073 mm; their minimum capacitor-reserve gap
is 1.591 mm, against the existing 1.5 mm requirement. These are geometric bounds,
not measured cable clearances.

Seventeen focused native tests passed, including material continuity, actual
manufacturing thickness probes, carrier-centreline placement, complete pitch
hardware, continuous registration containment and negative mid-path, nut-lift
and uncontained-material cases. The focused evidence is recorded as
`bf-optical-l-review.json`, `bf-optical-l-unit.log` and
`bf-optical-print-delta.json` in the collected review artifacts. This note does
not itself establish completion of the final saved-CAD, alternative-equipment,
optional-power, manufacturing/export or full release pipeline checks. Existing
restrictions on FC hosting with a directly attached MG-F10-A helix or obstructing
optional accessory power installation remain in force.

The two prints gain 799.817 mm³ combined, approximately 0.808 g at the provisional
PA12 density of 1.01 g/cm³. The broader upright and larger ear increase their
nominal sections, but the longer arm introduces a larger load lever. No measured
strength, stiffness, vibration retention, clamp torque, PA12 creep life,
adhesive retention or pointing stability is claimed. Check those properties on
the actual print and installed sensor; the mount remains manually aligned and
has no roll correction or self-levelling mechanism.
