# Actual propulsion datums — BG

The user chose simple **physical CAD dimensions** for repeatable testing instead
of the preceding simulation-only rounding. The later 150 mm span request
supersedes the intermediate 130 mm proposal.

| Dimension | BF | BG |
| --- | ---: | ---: |
| Main output-axis spacing | 131 mm | **150 mm** |
| Axis height from straight rail envelope-contact plane Z0 | 48.2 mm | **50 mm** |
| Driven output stub, quantity 2 | 24 mm | **34 mm** |
| Opposite output stub, quantity 2 | 14 mm | 14 mm |
| Input stub, quantity 2 | 18 mm | 18 mm |
| Gear centre distance / angle ratio | 16 mm / −3 | unchanged |

The paired servo/input module remains detachable. No extra printed part,
bearing, coupler, spacer or fastener is added. The frame feet extend laterally;
the bearing posts and shared servo wall follow the higher axes. The motor
carriers, stock horns/adapters, bought gears/bearings and mounting interfaces
retain their local shapes. Rear motor-wire loop reservations follow the new axes.

## Choice and trade-off

The transverse thrust lever grows by `150/131−1 = 14.50%`. The corresponding
moment from the same force component increases by that fraction. Angular
acceleration/handling do not follow from this alone: moved masses also change
inertia, and the vehicle aerodynamics remain unmeasured. Wider propulsor
separation also gives 19 mm more transverse room between the unchanged guards.

Modeled differences from BF, using unchanged density assumptions:

- Printed material: **+1.5940 g**.
- Two longer Ø3 steel rods: **+1.1168 g**.
- Accounted difference: **+2.7109 g**; no claim of measured installed mass.

The gear overhang increases. On the positive side, the small-gear tooth-face
centre remains at Y29 mm while the inner bearing centre moves from Y35.75 to
Y45.25 mm. The force-to-bearing-centre lever grows from **6.75 to 16.25 mm**.
Thus the short original stub is not reused. A longer shaft and printed support
can deflect more under gear force. No loaded deflection, strength or stiffness
qualification is claimed; the actual load path includes two separate stubs,
carrier clamps and PA12, not a continuous solid steel beam across both bearings.
Check loaded mesh, backlash and retained alignment with the assembled mechanism.
The modest added mass and unchanged part count support selecting 150 mm for
this prototype; a guaranteed dynamic-performance improvement is not asserted.

## Gear alignment and shaft preparation

Keep the bought gear axial planes unchanged. Moving the small gear outward with
the motor would reduce face overlap with its fixed input gear.

Positive-side propulsion-local Y coordinates (opposite side mirrored):

| Feature | BG nominal coordinate |
| --- | --- |
| Driver body / tooth face | 22.5…30.5 / 27.5…30.5 mm |
| Output gear body / tooth face | 21.5…31.5 / 26.5…31.5 mm |
| Driven stub | 21…55 mm |
| Driven stub's 0.5 mm-deep end flat | 21…26 mm |
| Output gear M3 set-screw axis | 24 mm from the central module Y0 |
| Inner bearing | 44…46.5 mm |

The rod projects 0.5 mm past the inner hub face; its 5 mm flat overlaps the
5 mm hub by **4.5 mm**, not 5 mm. The published screw axis lies inside the flat
with a minimum nominal end distance of **2 mm**. The flat stays clear of the
bearing journal. Shaft and gear move together through the carrier's existing
axial play; the bearing remains independently captured. Actual M3 length,
point, projection and clocking still require the received parts.

The complete external shaft/gear rotation reservation expands from pod-local
Y±44 to **Y±54 mm**. It must enclose the new shafts and relocated gear throughout
rotation; retaining the old clearance reservation would miss part of the mechanism.

## Datums and verification limits

`contracts/drive.py` owns the 150/50 mm layout. Exported simulation vectors are
read from the saved CAD rather than rounded. The common clamp seating shift is
still ±0.1 mm; exact vectors relative to the propulsion-pair reference and their
translation to the rail frame are both recorded in
[the simulation sheet](simulation_parameters.md). CV and actual installed CG
remain unmeasured. The rail-contact plane is not CV.

The independent old/new review, native tests, final saved assembly/export checks
and visual evidence belong to [BG verification](bg_design_verification.json).
They validate recorded nominal geometry and prescribed motion, not physical
fit, force-dependent mesh alignment, flexible wires, fatigue or flight readiness.
