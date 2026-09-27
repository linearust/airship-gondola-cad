# Common three-horn coupling — AU

This supersedes AS's single-horn adapter instructions. One printed adapter and
unchanged Ø3 mm input stub/gear plane accept any of the three drawings on either
side, including mixed pairs. [The horn contract](../gondola/contracts/servo_horns.py)
selects each side; changing
selection requires rebuilding the CAD, BOM and validation. Default is one original
PTK-pattern horn and one second metal horn because only one original was available.

| Bought horn | Used hole radii | Attachment |
| --- | --- | --- |
| [Original 15T/4 mm](selected_15t_4mm_horn_drawing.png), root Ø6.1 mm | 6.6 / 12.2 mm | Two existing M1.6 threads; M1.6×5 screws from adapter front |
| [Second metal 15T/4 mm](metal_15t_4mm_horn_6_98_drawing.png), root Ø6.25 mm | 6.98 / 12.98 mm | Two existing M1.6 threads; M1.6×5 screws from adapter front |
| [KST 0415.13](kst_0415_13_horn_drawing.png), root Ø6 mm | 4.5 / 13.2 mm | Enlarge these two existing pilot holes to Ø1.5 mm; reverse M1.4×6 screws and front M1.4 hex nuts |

The original/second outer radii repeat the drawing's 2.8/3.0 mm pitch and are not
independently dimensioned. KST's supplied holes alternate Ø0.8 mm at 4.5/8/11.5 mm
and Ø1.0 mm at 6.8/10/13.2 mm; **they are not M1.6 threaded holes**. Its
[manufacturer page](https://kstservos.com/products/0415-13-aluminium-servo-arm-for-4mm-15t-servo)
lists aluminium and 15T/4 mm. The original metal horn's X06 compatibility remains
the user's accepted premise; no received spline fit is certified.

The common 2.2 mm-wide radial slot has end centres 4.3/13.4 mm. The plate extends
to 16 mm, leaving a 1.5 mm end web beyond the rounded slot. Keep two screws,
separated by at least 4 mm, and tighten after centring the stub on the servo axis.
The slot takes hole-position differences; it is not intended to slide or remain
loose in operation. A C-shaped root seat clears all three roots. Nominal radial
clearances are 0.225/0.15/0.275 mm respectively; these are assembly limits, not a
precision concentric pilot. Actual runout and free gear mesh need inspection.

The front fastener seats are flat, with no recessed screw pockets. Adapter grip
is 3.6 mm. Threaded metal variants retain nominal 1.4 mm engagement and 0.2 mm rear
clearance with 5 mm screws. Require flat head bearing diameter ≥3.0 mm within the
existing Ø3.5 mm maximum head/1.6 mm height envelope. Do not reuse the prior 4 mm
nominal screw selection. Both metal variants use a 3.5 mm axial envelope; the
second drawing does not establish its 1.6 mm blade thickness. Check actual seating,
thread depth, length and back-side clearance before final fabrication.

KST's drawing gives a 1 mm blade and 3.5 mm overall height. Its end pilot holes are
enlarged on the detached horn, without transferring any new hole centres. The
minimum nominal ligament to an unused neighbouring hole is 0.55 mm; deburr without
tearing it and verify reversing-load retention. This is conditional preparation,
not an untouched drop-in claim or strength qualification. Other nearby hole pairs
were rejected because enlargement would nearly join their holes.

For KST require M1.4×0.3 screws with rear heads ≤Ø2.6×1.0 mm and front nuts with
AF 2.9–3.0 mm and height ≤1.2 mm. The user's assorted kit includes M1.4, but its head
size is not measured. The rear head/root gap is only 0.2 mm nominal, requiring
received-part inspection. Nut sizes follow the
[Fastenal DIN934 dimensional reference](https://www.fastenal.com/content/product_specifications/M.FHN.934.A4-80.01.pdf),
not a certification of the actual purchased lot. No washers are needed in the
nominal geometry; the two front nut lands support the slot. The local open shaft-
boss relief permits the near nut to rise off the bolt and exit sideways; it leaves
at least 1.10 mm nominal wall beside the D bore. Physical PA12 retention remains
unqualified. The full 1.5 mm shaft-stop floor and original shaft grip remain.

## KST assembly and service

Assemble the horn onto a servo **outside the bridge**: insert the reverse screws
into its pilot holes, fit the horn and correct OEM centre screw, then add the
adapter and front nuts. A rear holding-driver stem ≤Ø1.5 mm clears the bare servo;
a normal large screwdriver is not assumed to fit. Fine pliers/open tooling hold
the front nuts from the arm end. Actual tool tip/recess and handling remain checks.

Insert the servo+horn+adapter unit into the bridge, then secure the servo ears.
Narrowing the adapter plate to 10 mm and C-seat outer radius to 5 mm leaves the ear
screw and tool paths accessible without an extra centre access hole. Insert the
stub and gear last. For service remove the output gears and paired drive module,
remove the selected large gear/stub and ear fasteners, then move the complete
servo unit 12.5 mm gearward and 40 mm sideways. Only after the unit is clear of the
bridge should the KST front nuts be removed, outer first. Leave rear screws in
the horn while sliding the adapter forward beyond their tips. Reverse for assembly.

CAD checks cover nominal shared-solid compatibility, both mirrored drives,
selected hardware seating, sampled input angles −60..+60°, and the declared rigid
service paths. They do not establish spline fit, bolt preload, thread/PA12 strength,
root concentricity, fatigue, elastic deflection or loaded gear runout.
