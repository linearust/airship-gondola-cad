# Shared mounting plate

The [plate template](../gondola/parts/mounting_plate.py) and
[slot contract](../gondola/parts/mounting_slots.py) own exact geometry. Battery,
FC and navigation use identical 64×64×2 mm rounded square plates with integral
shoes. The optional power deck repeats the plate template on a different support.

The plate openings have quarter-turn and X/Y reflection symmetry; shoes and
clamps are directional. Retain complete FC bearing annuli, slot lands and
fastener-head travel beneath the plate. A pattern fitting one device does not
qualify an arbitrary occupied installation.

| Opening family | Nominal interface |
| --- | --- |
| FC | Four Ø2.6 bores on a 25.5 mm square, rotated 45°; Ø6.5 bearing annuli |
| Centre | One Ø2.6 spare bore; carrier has a blind side-loaded ordinary M2 nut seat |
| Inner diagonal | Four 2.6 mm slots for 16–23 mm square pitches; includes selected shifted P-AS axes |
| Large square | Four 3.6 mm arcs for 30.5 mm square pitch at ±15°; M3-width slots, not qualified for small M2 heads |
| Side | Twelve 2.6 mm slots on X=±27 or Y=±27; travel −23…−13, −5…5 and 13…23 mm |
| Outer diagonal | Four 2.6 mm slots for 40–45 mm square pitches |

There are five fixed bores and 24 slots. Minimum full-thickness lands and all
rounded slot ends are checked in native geometry. The carrier's central nut
must be loaded off rail; choose screw length from the actual stack and avoid
bottoming on its blind floor. The floor is not a torque stop. The spare joint
adds no fastener to the baseline inventory.

The centre bore splits battery and GPS adhesive allocations into uninterrupted
strips. The radio uses two separate underside strips beside the side-slot row.
Exact rectangles live in [equipment_mounts.py](../gondola/parts/equipment_mounts.py),
with optional-power contacts in their own contract. Checks must cover complete
plate backing and device overlap, not just total area. Do not restore a single
central patch across the bore or slots. Actual component-free PCB contact,
insulation, tape compression, retention, cooling and peel resistance remain
receiving/assembly checks.

Verify fixed annuli, slot head/shank travel, rail-key and nut-loading access,
optical/power foot seating and removal with the saved assembly. Nominal contact
and clearance do not establish PA12 strength, stiffness, creep or adhesive life.
