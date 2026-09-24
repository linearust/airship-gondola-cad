# Three-module layout and propulsion wiring — AN

Keep three independently positioned rail modules: central propulsion, a battery
carrier on one side, and the FC plus the currently dimensioned ancillary
electronics on the opposite side. The removable paired servo/input module
remains separate from the output-bearing frame. Do not merge electronics into
that replaceable servo bridge or add a tall FC stack merely to shorten leads.

`contracts/design.py:MODULE_STATIONS` owns the initial locations and discrete
carrier orientations. These are starting positions for physical trim, not a
measured centre-of-gravity result. The optical tower remains transferable
between the battery and electronics carriers through the existing structural
stack interface; its load does not pass through the battery or FC dampers.
There is no propulsion-frame optical host in this revision.

## Placement rationale

In neutral, both main motors face +X and their rear side is -X. The previous
FC on +X was on the opposite side from the rear motor-wire reservations.
Move the electronics to -X and the battery to +X. Turn the electronics carrier
so its P-AS arm extends outward instead of into the servos. Preserve the FC's
intended global installation orientation independently of that carrier turn;
the square mounting pattern permits it. The CAD envelope has no component
markings, so verify the actual board arrow and firmware orientation at assembly.

Carrier yaw reverses the world direction of its local rail clamp. Apply the
matching transverse seating offset and transform tool access in the correct
frame. The selected 0/180-degree carrier orientations are design choices, not
an arbitrary user-adjustable yaw joint. FC underbody and peripheral wiring
reserves follow the FC orientation; ancillary-device reserves follow their
own carrier. The XT30 body and unplugging space move to the side to avoid
the servo module.

The existing printed shapes, purchased hardware and integral rail shoes can
serve this rearrangement. A central elevated FC would require new supports
and additional service checks without a clear benefit over the rear placement.

## Variable battery load

Retain the separate battery carrier and its geometric adjustment. The modeled
pack and declared maximum envelope remain the dimensioned baseline, not a
promise that every capacity fits. Different packs require actual dimensions,
adhesive retention and renewed clearance/trim checks. An empty carrier may be
used for a separately engineered external-power setup; this layout change does
not select a PSU, certify electrical compatibility or account for cable/tether
loads. Do not add guessed PSU connectors or enlarge the envelope by capacity.

Actual battery, prints, hardware and harness masses are incomplete. Do not
claim that the three modules have equal mass, that propulsion is always the
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

Release evidence belongs to `tests/fixtures/rev_an_review.json` and matching
generated validation reports. Physical qualification remains separate.
