# BH design review

Intent: simplify the optical support, add a usable central carrier attachment,
use the supplied horn geometry and improve output-axis support. This is nominal
CAD review, not print, bearing-fit, strength or flight qualification. The existing
150 mm motor-pivot spacing, 50 mm contact-plane-to-pivot height, 48T/16T drive and
removable paired-servo/input module are retained.

## Optical support

The two carrier-foot bolts and offset pedestal are replaced by an integral
standard rail shoe, straight centreline post and pitch ear. The adhesive tray
remains separate for one manually locked ±20° pitch axis. Two printed parts,
one M2×8/nut rail clamp and one identical pitch pair; one fewer fastener pair.
The pivot is at native Z30 mm. Native +Z points away from the balloon/downward;
centred geometry does not automatically make the sensor vertical at flight trim.

The baseline rail station is X144 mm; direct tether installation uses X158 mm
for both sensor options. Both MTF-02P and MTF-01P retain adhesive attachment and
connector reserves. Relocation is a rail-position control, not arbitrary-placement
approval. The raised battery-host power portal can obstruct the field; rejected
combinations remain rejected. Consult the composed navigation/power/optical report.
Do not add a taller alternate pedestal merely to make every combination pass.

Disconnect the sensor lead before sliding the shoe off a rail end. Intervening
modules may need removal. The clamp, rail fit, pointing retention and PA12 creep
still require physical checks; no roll compensation or active levelling is provided.

## Central carrier attachment

The 64 mm symmetric universal plate gains a central Ø2.6 mm M2 clearance hole.
Its raised root contains an ordinary M2 hex-nut seat loaded through one lateral
port while off rail. A 1.5 mm blind floor remains above the rail-channel roof,
so the hole does not expose the rail to the screw tip. The nut pocket is a print
allowance, not an established delivered fit. Check this vertical nut seat on the
printed carrier with the received nut; the rail coupon uses a different nut
orientation and does not qualify this seat.

A nominal M2×5 through the bare plate leaves 0.4 mm clearance to the floor and 2 mm
to the rail. An added mounting stack changes the required screw length: measure
engagement and tip clearance; do not bottom the screw or use the floor as a
clamping stop. The optional central screw/nut is not in the baseline inventory.
The existing FC bores and 24 slots are retained. Battery and GPS adhesive contact
allocations avoid the central hole: four battery patches total 376 mm²; two GPS
strips total 168 mm². These are supported CAD areas, not adhesive load ratings.

## OEM horn adapter

Use the manufacturer-supplied half arm 1 STEP and its existing hole axes. The
backing is now a tangent rounded taper (root radius 5.15 mm; tip radius 2.8 mm at
13.2 mm), retaining the nominal blade face and front nut lands while removing
rectangular corners. Do not replace the purchased spline with a printed spline.

The open Ø7.3 mm root seat retains 0.15 mm nominal radial allowance. Near Ø1.8 mm
round opening at 6.8 mm constrains assembly movement; far 1.8×2.4 mm radial slot
at 13.2 mm absorbs pitch variation before tightening. Both existing Ø1 mm horn
holes are enlarged to Ø1.5 mm; rear M1.4×8 screws and front M1.4 nuts remain.
These clearances do not compensate a bent shaft, eccentric spline or running
misalignment. Check delivered seating/runout and free gear motion before tightening.
The shaft-stop floor, gear planes, input stub and ordered removal path are retained.
See [manufacturer evidence](servo_horn_compatibility.md).

## Output bearings and shafts

Each separate shaft stub passes through one bearing, but the whole rotating
carrier is supported at two sides. It must not be described or calculated as a
continuous rigid steel shaft: the connection between the stubs is the PA12 carrier.
Bearing width alone does not establish installed wobble; rod fit, bearing internal
clearance, grip, support geometry and printed-part stiffness all contribute.
[NSK fit/clearance guidance](https://www.nskamericas.com/tools-resources/abc-bearings/fits-and-internal-clearance/).

| Nominal dimension | BG | BH |
| --- | ---: | ---: |
| Bearing centre spacing per rotor | 59.5 mm | 75.5 mm |
| Gear tooth centre to nearest bearing centre | 16.25 mm | 8.25 mm |
| Shaft grip length | 5.5 mm | 13.5 mm |
| Straight post depth | 4.5 mm | 6 mm |
| Driven / idler / input stub length | 34 / 14 / 18 mm | 34 / 22 / 18 mm |
| Output-frame width | 216 mm | 232 mm |

Four existing 3×6×2.5 mm bearings, integral outer-ring shoulders/latches and separate
carrier axial stops remain; no spacers, extra bearings, caps or fasteners are added.
Symmetric carriers remain one common print. The shaft retraction before carrier
removal is now 14.5 mm; after carrier removal, an additional 20 mm extraction
clears the bearing without crossing the opposite drive. Follow the checked sequence.

This support change alone adds about 6.46 g of PA12 and 0.89 g of rod at the model
material densities; these are volume-based estimates, not weighed components.
The shorter gear overhang and longer grips improve the load-path geometry, but
no quantified stiffness, backlash or load rating is claimed. Check actual Ø3 rod
fit, bearing clearance, shield freedom, endplay and retention under reversing load.
A matching precision rod remains a fallback if the supplied rod does not fit.

All four changes together add approximately 7.45 g to the modeled print/hardware
subtotal (120.13 → 127.57 g under the same density assumptions). This excludes
unmeasured hardware/materials and is not the total gondola or vehicle mass.

## Evidence

[Verification manifest](bh_design_verification.json) records the final source,
CAD, tests and artifacts. The independent old/new shape, placement, native-control
and metadata review is retained with the BH regression fixture. Source/test success
does not close the physical qualification items in `design.release_status()`.
