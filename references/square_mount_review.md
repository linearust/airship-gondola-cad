# Square shared plates and compact optical pedestal — BB

User decision, 2026-09-28: a square plate with symmetric common mounting slots;
a much smaller optical adapter attached directly to that array; one alignment
axis is sufficient for a rail on the balloon's bottom centreline. This supersedes
AY's rectangular plate and two-axis diagonal optical portal. The printed rail,
propulsion, and intentionally removable servo/input-drive module are retained.

## Shared plate

Three identical rail carriers use a 64 × 64 × 2 mm plate with 3 mm plan corner
radii. Both outline and complete opening array have 90-degree rotational and
X/Y reflection symmetry. The rail shoe and clamp remain directional. XY coordinates
below are local to each carrier, not assembly coordinates.

| Interface | Geometry / coverage |
| --- | --- |
| Selected FC | Four fixed Ø2.6 mm M2-clearance holes, 25.5 mm square at 45° |
| Inner common pattern | Four 2.6 mm-wide diagonal slots, axis-aligned square pitch 16–23 mm |
| P-AS | Two 23 mm slot endpoints; body datum moves to (0, −2.2) mm to preserve the published hole coordinates relative to the board |
| Larger common pattern | Four 3.6 mm-wide arcs, 30.5 mm square with ±15° rotation from the plate axes |
| Outer common array | Eight 2.6 mm-wide M2 slots along X=±27 or Y=±27; centre travel −23…−13 and 13…23 mm along each side |

Four fixed bores and sixteen slots; no additional optical-only or power-only
carrier bores. This is a project mounting array, not a universal industry
breadboard or a complete Holybro X500 interface. 16–23 mm continuous coverage
is geometry, not certification of arbitrary modules. Documented examples include
[20 mm FPV stacks](https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/)
and [the F405-STD's 30.5 mm pattern](https://www.mateksys.com/?portfolio=f405-std).
Use the actual selected fastener/grommet arrangement; existing small M2 heads
are not approved for the M3-width arcs.

Required native plate checks include one valid solid, complete 1.5 mm slot-edge
lands and complete FC support annuli with Ø6.5 mm outer diameter. These are
geometric screens, not strength or clamp-pressure qualification; actual results
belong in the release evidence rather than an independently maintained prose total.

The plate underside is raised to Z=13.4 mm above the rail datum, with one plain
12 × 12 mm riser. This keeps M2 screw heads at the small-slot endpoints clear of
the rail shoe without countersinks, complicated pockets or weakened rail walls.
The common support face is Z=15.4 mm; equipment and wiring must follow this datum.

## Adhesive allocations

- Battery: 12 × 18 mm centre patch and two 16 × 10 mm patches at Y=±25; 536 mm² nominal contact.
- GPS alternatives: 12 × 14 mm at the navigation datum.
- Mini radio: 10 × 12 mm on the rail-facing underside at (26, −5); body at (26, −11), rotated 90° so its long axis follows Y. The 120 mm² patch is allocated on solid plate; the body and connector reserves are offset to avoid both rail-clamp approaches and optional-power foot service paths.

These are continuous available material regions, not measured device bearing
faces or qualified minimum adhesive areas. The radio body and 66 mm reference
battery overhang the plate. Shifted battery positions can cover less
of the nominal contact; actual retention, insulation, heat and balloon clearance
remain physical checks. Do not add dedicated cable-tie holes.

## Compact one-axis optical support

Two prints replace three: one rectangular foot with a short straight upright,
and the existing continuous 18 × 12 mm sensor tray. The foot uses two M2 pairs
through one ordinary outer carrier slot, at its two endpoints; a third M2 pair
clamps the single pitch-Y pivot. No roll stage, separate retaining piece or washer
is added. The base uses the carrier corner away from propulsion in both supported
host orientations, rather than crossing the FC with a broad diagonal portal.

The planning range is ±20° about the transverse Y axis. It corrects longitudinal
curvature only, assumes the rail centreline placement, and does not provide
self-levelling or roll correction. Align the actual sensor downward at operating
trim and lock the joint. The two supported hosts remain battery and FC; generic
hole compatibility alone does not qualify other hosts or another plate corner.

The final pivot is 22 mm above the host support, on an 8 × 16 mm foot shifted
1 mm inward relative to its two clamp axes. Without optional power, P-AS and
MG-A01 permit both optical hosts. A directly attached MG-F10-A helix permits the battery optical host only:
its reserved space intersects both sensor fields on the FC host. Failed FC-host
rows remain visible in the compatibility evidence. A remote antenna's actual
location, harness and effect on optical clearance remain unmodeled.
Optional power can further limit the optical-host choice; a platform on the
accessory carrier can obstruct the FC-host field. Each power plan must retain its
permitted and rejected combinations, and the illustrated installed combination
must pass independently.

MTF-02P and MTF-01P remain alternative adhesive-mounted sensors. Retain whole-body
optical screens, plug access, fastener-tool access and foot registration checks.
Service requires disconnection and a bench-supported host, removing both foot
fasteners and following the prescribed slide/lift path checked by the validator. Do not assume a straight
lift through the FC's connector working space is clear.

The optional power platform still has a separate integral portal, using opposed
outer common slots and the same square top plate. It is excluded from the
baseline BOM and cannot share the installed optical host. Its acceptance depends
on the separate saved optional-power report and each plan's explicit permitted
hosts; common hole geometry does not make every power/navigation/optical
combination usable.

## Verification boundary

The [BB verification record](square_mount_verification.json) binds the reviewed
transition, final source, native test coverage, saved CAD, exported print files,
optional-power checks and Blender derivative. It retains the earlier failures and
the complete rerun of the corrected radio-test module; this is not presented as
a second successful whole-suite invocation. Detailed evidence is retained in
[square_mount_checks.json.gz](square_mount_checks.json.gz).

AY restoration remains historical in [its retained review](slotted_mount_restoration.json).
Physical PA12 fit, strength, creep, real fastener bearing, adhesive retention,
installed flexible-cable motion, sensor calibration and flight qualification
remain unverified. Geometric acceptance does not certify these physical limits.
