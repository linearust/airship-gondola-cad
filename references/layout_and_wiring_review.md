# Equipment layout and wiring — purchased-adapter redesign

This reference describes the current intended architecture. Exact stations,
orientations and quantities belong to
[design.py](../gondola/contracts/design.py); matching generated reports establish
geometric test status. Older AX identical-carrier and underside-radio results
are historical and do not validate this revision.

## Layout and supported interfaces

Keep the three functional mass regions: central propulsion, battery on +X, and
FC plus other electronics on -X. In neutral the motor backs face -X, bringing the
FC toward the lead exits. The separate accessory carrier groups the selected
navigation device and Mini in that electronics region. These are initial design
positions, not a measured centre of gravity or a claim of equal regional mass.
Preserve the intentional separation of the paired servo/input-drive module from
the propulsion/output-bearing frame.

The FC uses the bought carbon adapter on a small raised saddle. Its 25.5 mm axes
are on the carbon; two opposed 16 mm axes secure the carbon to the printed saddle.
Four printed pads support that plane. Rigid clamps remain independent of FC
soft mounting. The carbon is conductive, its undimensioned cutouts remain
unmodeled, and its full square envelope does not prove bearing material. See the
[purchased-part review](stock_stack_adapter_review.md). The 8 mm lowest-component
wiring allowance is not a verified PCB bearing plane or complete damper stack.

Battery and accessory use smaller continuous insulating decks with the same
rail shoe. Their roles do not require identical plate outlines or redundant hole
patterns. Navigation and Mini share the accessory's outer face with distinct
adhesive regions and connector paths; there is no inverted radio, separate radio
tab or long navigation branch. Exact geometry is in
[equipment_mounts.py](../gondola/parts/equipment_mounts.py) and
[equipment_layout.py](../gondola/parts/equipment_layout.py).

The optical fixed support is integral with the selected battery or FC carrier.
Changing host requires the corresponding carrier variant and transfer of the
movable sensor head, followed by recalibration. Its load does not use the FC
PCB or battery as a structural support. There is no propulsion or accessory
optical host. Optional power similarly replaces a low carrier with an integral
variant; optical and power structures cannot share one host.

## Near-end accessory station and trim

The selected accessory centre is X = **-159 mm**. Its 18 mm shoe spans
**-168 to -150 mm** on the nominal -170 to +170 mm rail, leaving **2 mm** at the
nearest end. Only that much additional outward travel preserves full shoe
engagement. This is a local geometric limit, not a promise of broad adjustment,
a physical end stop or a holding-force qualification.

Its clamp lies 3 mm from the nearest solid rail-land centre. Do not move it to
an arbitrary point between lands: the rejected -152 mm trial had acceptable
optical separation but put the clamp 8 mm from a land centre. Inward movement
also requires renewed direct-helix, optical-field, connector and service checks.
Do not interpret the allowable land offset as symmetric free travel around the
chosen initial station.

The upper accessory deck projects 7 mm beyond the rail end. It does not mate
with that end; the complete shoe provides engagement. An optional upper power
structure may extend farther while using the same supported shoe. Check each
printed part against the 340 mm size limit, rather than confusing overall
assembly overhang with a single-part manufacturing dimension. Actual load,
stiffness, print distortion and creep still need physical assessment.

The [retained station review](stock_stack_adapter/accessory_station_review.json)
separates nominal service evidence, rejected intermediate probes and subsequent
verification. It is not a production-release declaration. Use final matching
reports for the accepted arrangement and optional power geometry.

## Frames, attachment and service

The selected carrier yaw reverses its local clamp approach in world coordinates.
Preserve the corresponding transverse seating offset and transform tool paths in
the actual parent frame. A 0/180-degree installation choice is not an adjustable
yaw joint. The square FC pattern also does not establish board heading: verify
the physical arrow and firmware orientation independently of carrier yaw.

The rail's tape wings attach the rail to the balloon. They are interrupted by a
raised running head and are not a continuous flat electronics mounting surface.
The role decks provide defined insulating contact away from that mating profile.
Declared adhesive patches, body envelopes and connector reserves do not qualify
actual backside contact, compressed tape, strap pressure or installed cables.

Release the rail clamp and use the checked end-removal sequence before servicing
a detached carrier. The integral optical support stays present during staged FC
or battery extraction: remove the movable optical head when required, release
device retention, lift enough to clear it, then translate through the open side.
The bought FC plate and rigid clamps remain installed. A straight lift through
the fixed beam is not an alternative. The low accessory permits outward bare
navigation/radio removal; the optional power variant has a different lateral
bench-service path below its fixed deck. Disconnect leads first in either case.

## Battery changes and wire management

Keep the declared battery envelope and placement allowance. Another capacity or
PSU arrangement needs actual dimensions, retention, wiring and renewed trim
checks. An empty battery carrier does not qualify tether loading or select a
power architecture by itself. Actual pack, print, hardware and harness masses
remain incomplete; choose final stations from measured masses and lever arms.

Motor leads move with the tilting carriers; servo cases and their leads remain
stationary. Provide motor-side strain relief, a free transition outside the
rotor/gear motion, and stationary strain relief before FC solder joints. Use
suitable existing broad members and bought ties, avoiding bearing latches,
shafts, gears and the servo-module removal path. Retain FC underside access,
insulation/damping and ESC ventilation.

The [propulsion wiring model](../gondola/parts/propulsion_wiring.py) and
[wiring reservations](../gondola/parts/wiring_reserves.py) describe connected
planning space. They do not establish unpublished lead exits, a completed tie,
actual cable length, bend radius or the flexible loop's changing shape. Recheck
routes after rail adjustment. Test rubbing, tension, twist and fatigue with the
actual harness through both bounded endpoints and independent opposite motor
poses. Identical rigid poses at -180 and +180 degrees do not have identical wire
winding. A short neutral line is not evidence of safe moving-wire behavior.

## Source references

- [MicoAir 45A installation guidance](https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-45a-manual): board orientation, damping, insulation and ESC ventilation. The [controller review](controller_selection_review.md) preserves the input-range conflict and unverified received hardware.
- [igus cable installation guidance](https://www.igus.com/contentData/wpck/pdf/US_en/7_guidelines_for_continuousflex_cables.pdf): general motion-space, strain-relief and tension principles. That cable-carrier system does not qualify this miniature free loop.
