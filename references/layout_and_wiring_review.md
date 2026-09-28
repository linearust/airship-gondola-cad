# Three mass regions and universal electronics carriers — AX

Keep three mass regions: central propulsion, battery on one side and electronics
on the opposite side. Two independently positioned carriers occupy the
electronics region: the FC/optical-host carrier and one carrier for navigation
plus the LR24-F-Mini. Battery, FC and navigation now use three copies of the same
printed shape and hole layout. Four rail shoes do not imply four
separate mass regions. The intentionally removable paired-servo module remains
separate from the output-bearing frame.

`contracts/design.py:MODULE_STATIONS` owns the initial locations and discrete
carrier orientations. These are starting positions for physical trim, not a
measured centre-of-gravity result. The optical tower remains transferable
between the battery and electronics carriers through the existing structural
stack interface; its load does not pass through the battery or FC dampers.
There is no propulsion-frame optical host in this revision.

## Placement rationale

In neutral, both main motors face +X and their rear side is -X. Keep the
electronics on -X and the battery on +X. The electronics carrier is turned
180° about Z to retain the existing optical-host orientation. Preserve the FC's
intended global installation orientation independently of this carrier turn;
the square mounting pattern permits it. The CAD envelope has no component
markings, so verify the actual board arrow and firmware orientation at assembly.

AX retains the AW initial FC carrier station at X = -54 mm, with navigation
at -158 mm. The earlier move from X = -72 mm increased separation from the centred navigation
and optional direct helix, and brings the FC closer to the neutral motor-lead
exits. The new shoe position coincides with a rail land centre. These are initial
placement choices; optical-field, service and wiring clearance checks still apply,
and the positions do not establish mass balance or installed cable lengths.

Carrier yaw reverses the world direction of its local rail clamp. Apply the
matching transverse seating offset and transform tool access in the correct
frame. The selected 0/180-degree carrier orientations are design choices, not
an arbitrary user-adjustable yaw joint. FC underbody and peripheral wiring
reserves follow the FC orientation; ancillary-device reserves follow their
own carrier. The XT30 body and unplugging space move to the side to avoid
the servo module.

The shared carrier combines a 54 × 74 mm deck with 3 mm plan-view corner radii
and an integral rail shoe, with no projecting tab or model-shaped pockets.
The plate outline is symmetric, while holes and clamp orientations retain their
functional datums. Every instance has the same confirmed
FC/P-AS axes, standard square patterns and six expansion bores. The navigation
instance places P-AS or one GPS at its centre, and the Mini at (-15,28) mm on the
opposite plate face, beside the rail shoe. It needs no radio-specific plate. See
[common carrier rationale](universal_carrier_review.md) for the hole and support
boundaries. The Mini's X offset leaves rail-clamp hex-key access and clears the
diagonal stack-foot bolt from its connector lane without changing the plate outline. Its ordinary rail clamp
permits independent positioning. The navigation carrier starts near the aft
rail end to separate the optional helix
from the optical hosts; recalculate the field-of-view and connector checks after
layout changes rather than reusing older results. The initial accessory
shoe is 4 mm from its rail land centre; it is not a claim of ±4 mm free adjustment
around that initial position. Recheck the land, whole shoe support and all
clearances after moving any carrier.

The rail's 32 mm wide pads are 14 mm long, with a raised central running head;
the side wings carry attachment tape to the balloon. They are not a continuous
flat 32 mm electronics mounting face. The common carrier provides a
known geometric adhesive face without covering the sliding head or using the
rail's balloon-contact underside. The Mini uses the carrier's face toward the
balloon, outside the shoe. Its body starts 4.6 mm from the Z = 0 reference plane
and its inverted connector reserve starts 2.6 mm from that plane. Neither
dimension proves clearance to the actual balloon or installed plug. The actual
device contact, strap path and adhesion remain unverified. Remove the carrier
and service the Mini on a bench; do not assume access while attached to the
balloon. All three carrier structural datums remain centred at (0,0), but
the navigation instance remains excluded as an optical host. The same physical
print does not clear the equipment attached to it from the optical field.

## Variable battery load

Retain the separate battery carrier and its geometric adjustment. The modeled
pack and declared maximum envelope remain the dimensioned baseline, not a
promise that every capacity fits. Different packs require actual dimensions,
adhesive retention and renewed clearance/trim checks. An empty carrier may be
used for a separately engineered external-power setup; this layout change does
not select a PSU, certify electrical compatibility or account for cable/tether
loads. Do not add guessed PSU connectors or enlarge the envelope by capacity.

Actual battery, prints, hardware and harness masses are incomplete. Do not
claim that the three regions have equal mass, that propulsion is always the
heaviest, or that symmetric spacing guarantees balance. Choose rail positions
from measured mass and lever arms, then recheck all clearances and wiring.

## Wire management boundary

Motor leads move with the tilting carrier; servo cases and their leads stay
stationary. Keep motor strain relief on a suitable carrier feature, a free
flexible transition outside the rotor/gear sweep, and stationary-side strain
relief before the FC solder joints. Prefer existing broad printed members and
small bought ties; do not fasten to bearing hooks, shafts, gears or across the
servo-module removal path. A stationary electronics carrier can anchor the
downstream portion without a needless detour to the low propulsion-frame foot.

The connected CAD reservations describe available loop workspace and a route
toward the FC. They do not establish the motor's unpublished lead-exit datum,
an installed tie, cable length, bend radius, or the flexible cable's changing
shape. Fixed routing must be revised after rail adjustment. Moving-wire
clearance, rubbing, tension, twist and fatigue need the actual harness through
the entire bounded travel and independent opposite motor poses. Equal rigid
poses at -180 and +180 degrees do not make those winding states interchangeable.

Retain FC underside access, insulating/damping hardware and ESC ventilation.
Do not use a short direct line in the neutral pose as evidence that a moving
wire route is safe.

## Primary references

- [MicoAir 45A installation guidance](https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-45a-manual): board orientation, insulation/damping and ESC ventilation. See `controller_selection_review.md` for the unchanged nominal interface, changed included dampers and unresolved input-voltage evidence.
- [igus cable installation guidance](https://www.igus.com/contentData/wpck/pdf/US_en/7_guidelines_for_continuousflex_cables.pdf): motion space, avoidance of tensile loading and strain relief. General principles; the cited cable-carrier system does not qualify this miniature free loop.

Current geometric evidence belongs to `tests/fixtures/rev_ax_review.json` and
matching generated validation reports. Until those checks are complete, this
reference describes the intended layout and its limits, not a passed release.
Physical qualification remains separate.
