# Universal equipment carrier — AY

The user wants identical, expandable plates with simple outlines. AY moves the
nominal structural tower feet inside the existing plate and replaces generic fixed-hole
rows with shared mounting slots. Confirmed FC/P-AS axes remain fixed. Preserve
the deliberately separate servo/input-drive and propulsion/output-frame modules.

## One carrier shape

Battery, FC and navigation use identical printed carriers: a 54 × 74 × 2 mm
rounded rectangular deck with 3 mm plan-view corner radii, one integral rail shoe
and the same structural datum at (0, 0). There is no projecting radio tab or
outboard structural clamp ear. Only the outline is symmetric; device positions
and the rail clamp retain their prescribed orientation. Different instance names
and equipment allocations do not imply different printed shapes.

The FC's 8 mm underbody design reservation, rail mating profile and equipment
support height remain unchanged. Battery envelope and adjustment bounds are
unchanged. Spare slots do not enlarge the qualified equipment envelope or turn
perforated areas into continuous adhesive support.

The shared plate template contains:

- Six fixed Ø2.6 mm clearance bores on the confirmed FC/P-AS axes, each with its
  full Ø6.5 mm support region preserved. The clearance diameter is a project M2
  provision, not a claim that the original device holes have that diameter.
- Four M2 radial slots providing square-pitch coverage from 20 to 24 mm at a
  fixed 30° pattern orientation. The 20 mm pitch has a retained manufacturer
  reference; the full 20–24 mm range is geometric adjustment, not a claim that
  every intervening pitch belongs to a compatible catalog board. Smaller inward
  positions were rejected because the rail shoe obstructed the M2 screw heads.
- Four M3 arc slots preserving a 30.5 mm square pitch while allowing its pattern
  to be clocked ±15°. They do not permit independent arbitrary hole placement.
- Two opposed M2 side slots replacing the former six discrete expansion bores.
  Their spacing and centre travel are project provisions, not a PCB standard.

The two circular structural foot-clamp bores are separate from those six bores
and ten slots. They remain rigid fastening locations rather than generic
adjustment slots. Exact dimensions, datums and swept slot geometry belong to
[mounting_slots.py](../gondola/parts/mounting_slots.py), device axes and support
allocations to [equipment_mounts.py](../gondola/parts/equipment_mounts.py), and the
structural joint to [stack_interface.py](../gondola/parts/stack_interface.py).

The [Holybro reference review](holybro_x500_plate_review.md) distinguishes the
X500 V1 plate from the current V2 #31109. The V2 plate is 93 × 65 mm and has a
different radial-slot layout. Its complete outline and pattern are not copied:
they would enlarge this carrier and cut through useful support. These are
project-specific provisions inspired by that approach, not a drop-in X500
interface or a newly established industry standard.

## Support, fastening and the structural tower

Slot travel is for selecting an assembly position before tightening, not movement
in operation. Choose actual heads, nuts, standoffs and insulation after checking
the board, adjacent fasteners and underside access. Existing M2 heads are not
automatically suitable for the M3-width arcs. No extra baseline fasteners,
washers, printed threads or dedicated cable-tie features are selected.

Keep the declared continuous adhesive patches. The battery allocation is a
16 × 18 mm centre patch plus two 16 × 7 mm end patches at Y = ±23 mm: the total
512 mm² is unchanged, but its distribution avoids the new slots. GPS retains
its 18 × 14 mm centre allocation. The Mini retains its 22 × 14 mm opposite-face
allocation. These are geometric support regions, not measured device contact
faces or qualified adhesive strength. Do not bridge a slot and count it as
continuous load-bearing contact.

The common optical/power portal is narrower in plan so its broad feet and both
M2 clamp bores fit within the rectangular plate at nominal alignment. Its 32 mm
rise is unchanged.
The feet align with local Y and seat directly on the deck. Each has one 5 mm
45° cut across its inward corner to clear the FC underbody wiring reservation
while lifting the tower for service. This functional relief retains the complete
leg support and both clamp datums; it is not a lightweight lattice or another
part. The portal's diagonal orientation does not require projecting tabs. Two existing M2×8 screws
and ordinary M2 nuts still clamp the joint, independently of FC dampers. No new
parts or locating latch are added. Registration, complete foot seating, nut/key
access and removal paths must be checked with the revised joint. Print flatness,
clamp retention and PA12 creep remain physical acceptance checks. Permitted
pre-clamp registration can leave a foot edge slightly beyond the deck; the full
nominal contact area is not guaranteed at every allowed offset. Require flat,
stable seating and sound actual fastener bearing without rocking or slip.

The optional power platform uses the same deck outline and bore/slot template
with its integral tower instead of a rail shoe. Its regulator regions stay at
Y = ±13 mm. Shared deck geometry does not make the complete power tower and rail
carrier the same print. Slot cuts that cross the top beam must continue through
the fused support beneath the deck; verify the remaining structural sections.

## Shared interfaces, distinct installations

Identical carriers can exchange roles without choosing a different print. A
common interface does not qualify every payload, host or stack height, nor
simultaneous installation of devices whose patterns fit. No speculative extension
adapter or extra baseline fastening hardware is needed.

The Mini remains at accessory-local (-15, 28) mm on the face opposite navigation,
outside the rail shoe. Its body slightly overhangs the edge and rounded corner;
the declared adhesive allocation stays within the plate. The X offset preserves
rail-clamp access. Navigation remains centred on the other face. Recheck the
Mini, its connector lanes and tools against AY's relocated structural clamps and
new cuts, including permitted joint registration. See
[radio installation limits](radio_module_compatibility.md).

The radio's populated face points toward the balloon. Its nominal body starts
4.6 mm from the Z = 0 rail reference plane, and the connector reserve starts
2.6 mm from that plane. These are offsets, not clearances to a measured envelope
or installed plug. Attach and service it with the carrier removed on a bench;
on-balloon access, IPEX plug height, flexible pigtail and strap route remain
unqualified.

The navigation carrier remains excluded as an optical host. Optical and power
towers cannot share one host simultaneously. A direct MG-F10 helix and the
accessory power tower remain an excluded combination. Current saved-assembly
validation must establish the permitted host/profile combinations after this
change; a common attachment datum alone is insufficient.

## Evidence boundary

FC/P-AS source dimensions belong to `contracts/equipment_interfaces.py`;
`mounting_slots.contract()` retains the reference square-pattern sources and
project adjustment ranges. Outline, face assignment, clearances and adhesive
allocations are design choices. AY results belong to
`tests/fixtures/rev_ay_review.json` and matching generated reports. Until those
are complete, this reference describes intended geometry, not a passed release.
CAD checks do not qualify adhesive strength, loaded extension or tether anchors,
RF performance, actual fastener stacks, material life or received-part fit.
