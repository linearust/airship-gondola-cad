# Three mass regions and universal electronics carriers — BB

Keep three mass regions: central propulsion, battery on one side and electronics
on the opposite side. Two independently positioned carriers occupy the
electronics region: the FC/optical-host carrier and one carrier for navigation
plus the LR24-F-Mini. Battery, FC and navigation now use three copies of the same
printed shape and mounting layout. Four rail shoes do not imply four
separate mass regions. The intentionally removable paired-servo module remains
separate from the output-bearing frame.

`contracts/design.py:MODULE_STATIONS` owns the initial locations and discrete
carrier orientations. These are starting positions for physical trim, not a
measured centre-of-gravity result. The compact optical pedestal remains transferable
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

BB retains the initial FC carrier station at X = -54 mm, with navigation
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

The shared carrier is now a 64 mm square with a symmetric bore/slot array and
simple raised centre support. Its P-AS datum is (0,-2.2) mm and the underside Mini
is at (26,-11) mm, with its long axis along Y and its 10×12 mm adhesive patch
at (26,-5). This clears both rail-clamp approaches and optional-power foot
service. The common plate sits 2 mm
higher than AY to clear heads at the 16 mm slot pattern; device and reserve
heights follow the shared datum. [Square mount review](square_mount_review.md)
defines these changes and the compact one-axis optical pedestal.

The three prints remain identical, while role-specific equipment and rail poses
differ. Optical attachment is directly to one common outer slot; it no longer
uses the centred diagonal portal. The optional power platform retains a separate
portal on the same common slot array. Inspect each chosen host and optical screen.

The rail tape wings are not a verified flat device mounting surface: a raised
running head and flexible segmented contact remain. Adhesive devices use declared
solid regions on the shared carrier instead.

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
toward the FC. BB uses a propulsion-local intermediate waypoint at
(-42, ±12, 42) mm, raised 2 mm with the new carrier deck. This avoids entering
the FC connector reserve before the terminal connection region. The corridor is
a planning reservation; it is not an installed harness, cut length or verified
flexible-wire sweep.

These reservations do not establish the motor's unpublished lead-exit datum,
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

Current geometric evidence belongs to `tests/fixtures/rev_ay_review.json` and
matching generated validation reports. Until those checks are complete, this
reference describes the intended layout and its limits, not a passed release.
Physical qualification remains separate.
