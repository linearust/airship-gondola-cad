# Universal equipment carrier — AX

Historical AX record, superseded by the
[AZ purchased-adapter redesign](stock_stack_adapter_review.md). The identical
54×74 mm decks, separate optical feet and underside radio below are not current
assembly instructions. Current role carriers and service paths are documented
in [the layout review](layout_and_wiring_review.md).

The user requested interchangeable mounting plates, useful spare mounting holes
and modular expansion, then rejected the asymmetric radio landing tab. AX removes
the tab and uses both faces of a simple symmetric plate. Preserve the deliberately
separate servo/input-drive and propulsion/output-frame modules.

## One carrier shape

Battery, FC and navigation use identical printed carriers: one 54 × 74 × 2 mm
deck with 3 mm plan-view corner radii, one integral rail shoe and the same
structural stack datum at (0, 0). There is no side tab, separate radio bracket
or additional fastener. Only the plate outline is symmetric: the hole set and
rail-clamp interface retain their prescribed orientation.
Role-specific object names and equipment reservations do not imply different
printed geometry. The FC keeps its existing 8 mm underbody design reservation;
the rail mating profile and equipment support height are unchanged.

The longer rectangular deck supports the underside radio allocation without a
narrow branch and retains the common hole set. Its outer hole rows retain
2.7 mm nominal material to the X edges. The battery's declared maximum envelope
and adjustment remain unchanged; the larger outline does not turn perforated
areas into continuous adhesive support or qualify a different battery.

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

The Mini uses the accessory plate's opposite face at local (-15, 28) mm, outside
the rail shoe. Its 22 × 14 mm adhesive allocation has the same centre and is
clear of the existing holes. The body slightly overhangs the plate edge and
rounded corner; the complete adhesive region remains on the plate. Navigation remains centred
on the original face. The -15 mm X offset leaves access for the rail-clamp hex key
and keeps the connector lane away from the diagonal structural-foot bolt;
it does not alter the symmetric outline or common
hole datums. This arrangement separates the radio body and connector
reservations from the navigation region in height, without moving the navigation
datum or restoring a projecting branch. See
[radio installation limits](radio_module_compatibility.md).

The radio's populated face points toward the balloon. Its nominal body starts
4.6 mm from the Z = 0 rail reference plane, and the declared connector reserve
starts 2.6 mm from that plane. Those are geometric offsets, not clearances to
an actual envelope or a measured installed plug. The balloon, IPEX plug height,
flexible pigtail and strap route remain unmodeled. Attach and service the Mini
with the carrier removed on a bench; on-balloon access is not qualified.

The accessory carrier remains excluded as an optical host because navigation
and its possible antenna need their own optical-clearance review. Optional power
and optical towers cannot share one host simultaneously. A directly attached
MG-F10 helix and the accessory power tower also remain mutually exclusive.

## Evidence boundary

Common pattern sources are retained in `stack_interface.BOARD_PATTERNS`; FC and
P-AS source dimensions belong to `contracts/equipment_interfaces.py`. Carrier
outline, face assignment, clearance bores, expansion rows and adhesive allocations
are design choices. CAD tests screen modeled contacts, sections, reservations, host changes
and print outputs. They do not qualify adhesive strength, PA12 creep, loaded
tether anchoring, RF performance, actual fastener stacks or received-part fit.
