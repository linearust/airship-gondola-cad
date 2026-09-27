# Universal equipment carrier — AW

The user requested interchangeable mounting plates, useful spare mounting holes,
modular expansion and removal of the long dedicated radio platform. Preserve the
deliberately separate servo/input-drive and propulsion/output-frame modules.

## One carrier shape

Battery, FC and navigation use identical printed carriers: one 54 × 54 × 2 mm
deck, one integral rail shoe, the same structural stack datum at (0, 0), and a
straight 22 × 30 mm general-purpose tab extending from local Y = 24 to 54 mm.
Role-specific object names and equipment reservations do not imply different
printed geometry. The FC keeps its existing 8 mm underbody design reservation;
the rail mating profile and equipment support height are unchanged.

The 54 mm deck increases the previous battery support length slightly while
accommodating the common hole set and navigation alternatives. Its outer hole
rows retain 2.7 mm nominal material to the edge. The 66 × 18 × 17 mm maximum
battery reference still overhangs the deck: this is a permitted envelope, not a
claim of full-length support, measured battery dimensions or qualified retention.

All carriers have the same centred 20 mm M2 and 30.5 mm M3 square patterns,
the selected FC's 25.5 mm axes, and the confirmed P-AS mounting axes. Two short
rows of M2 clearance holes provide a 10 mm longitudinal pitch for future
attachments. The rows are a project provision, not an industry-standard PCB or
breadboard interface. These are 20 shared device/standard/expansion bores in
total; two additional structural foot-clamp bores belong to the tower joint.
Exact bores, rotations, coordinates and declared adhesive patches belong to
[equipment_mounts.py](../gondola/parts/equipment_mounts.py) and
[stack_interface.py](../gondola/parts/stack_interface.py); do not maintain a second
independent dimensional definition here.

The extra holes have a cost: reduced contact area, local sections and possible
fastener interference. Keep the declared solid adhesive patches rather than
assuming an unbroken tape strip. The centre holes of the two expansion rows are
close to the FC's transverse mounting axes; a bore fit does not establish room
for a simultaneous extension fastener beside a received FC damper. Choose free
holes after checking actual heads, nuts, spacers, insulation and wiring. No
printed threads, installed expansion hardware or dedicated tie holes are added.

The optional power platform uses the same deck outline and 20-hole template,
with its integral tower instead of a rail shoe. Its two regulator regions are
centred at Y = ±13 mm, keeping the BEC12S-PRO and SVPDB-8S body envelopes apart.
Shared plate geometry does not make the complete tower and rail carrier the
same print. Hole cuts cross parts of the tower's top beam below the deck; inspect
the fused supporting shape, rather than assuming the original beam is unchanged.

## Shared interfaces, distinct installations

The same carrier can be exchanged between rail stations without selecting a
role-specific print. Standard board holes can accept a future board or purchased
standoffs after its complete installation has been checked. Existing removable
optical and power towers retain their structural feet, independently of PCB
dampers. A common pattern does not make every payload, host or stack height
interchangeable without clearance checks. No additional speculative extension
adapter or extra baseline fasteners are required.

The Mini uses the accessory instance's generic tab with insulating adhesive or
an externally wrapped restraint; it has no dedicated plate. Navigation sits at
the carrier centre. This keeps the radio's two connector lanes outside the
conservative direct MG-F10 antenna reservation. Battery and FC instances have
the same tab available for other uses, but arbitrary equipment there is not part
of the modeled installation. See [radio installation limits](radio_module_compatibility.md).

The accessory carrier remains excluded as an optical host because navigation
and its possible antenna need their own optical-clearance review. Optional power
and optical towers cannot share one host simultaneously. A directly attached
MG-F10 helix and the accessory power tower also remain mutually exclusive.

## Evidence boundary

Common pattern sources are retained in `stack_interface.BOARD_PATTERNS`; FC and
P-AS source dimensions belong to `contracts/equipment_interfaces.py`. Carrier
size, tab, clearance bores, expansion rows and adhesive allocations are design
choices. CAD tests screen modeled contacts, sections, reservations, host changes
and print outputs. They do not qualify adhesive strength, PA12 creep, loaded
tether anchoring, RF performance, actual fastener stacks or received-part fit.
