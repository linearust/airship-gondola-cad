# Manufacturer X06 stock half-arm coupling — BE

Both sides use **X06 half arm 1**, selected from the four nominal STEP models in
the manufacturer's [archive](manufacturer/kst_x06_servo_horns_2026-09-28.rar)
supplied by the user; its [provenance record](manufacturer/kst_x06_servo_horns_2026-09-28.json)
retains the four source filenames and hashes. The current
[horn contract](../gondola/contracts/servo_horns.py) selects this one shape. Its
[retained STEP](../gondola/data/kst_x06_half_arm_1.step) is the purchased-part
geometry source, including the spline, hub, rounded edges and factory holes.
SHA-256: `ea9ad94160411df4c32e495eda85f75a43bcfcb379a86b113ad6e03c8aa79c81`.
The installed model changes only the two declared hole diameters below.

Half arm 1 has a flat front seat and a compact envelope. Half arm 2
places its spline on the opposite side of the supplied coordinate system and
needs a stepped front seat when oriented onto the servo. The two cross arms add
unused arms and a larger swept envelope. The selected half arm needs no printed
spline, separate centring component or stepped adapter seat.

| Nominal source feature | Dimension |
| --- | --- |
| Overall length / maximum root width | 18.7 / 7 mm |
| Rear hub diameter / total height | 6.5 / 3.5 mm |
| Arm thickness / arm rear plane in horn coordinates | 2 / 1.5 mm |
| Factory plain holes: radius → diameter | 4.5 → 0.8; 6.8 / 10 / 13.2 → 1 mm |
| Selected attachment axes | 6.8 and 13.2 mm; separation 6.4 mm |

The source coordinates map to the horn frame as X = source X,
Y = source Z + 1.5 mm, Z = −source Y. The spline opens toward the servo; the
flat front lies at Y = 3.5 mm. The original Ø3 mm input stub and gear planes stay
in place. Manufacturer nominal geometry does not establish delivered tolerance,
actual installed seating, root concentricity, resin, mass or loaded performance.
The horn is plastic; no density is inferred from that description.

## Preparation and adapter

On the detached horn, enlarge **only the existing Ø1 mm holes at 6.8 and 13.2 mm
to Ø1.5 mm**, preserving their axes; deburr and inspect the plastic. Leave the
4.5 and 10 mm holes and the purchased spline unchanged. These are plain holes,
not M1.4 or M1.6 factory threads. The minimum nominal planar ligament to an unused
hole is 1.15 mm: 2.3 mm centre spacing minus radii 0.75 and 0.4 mm. This geometric
margin is not a drilling-quality, preload or strength qualification.

The dedicated adapter has two separate radial slots, each 1.8 mm wide with end
centres ±0.3 mm from its factory axis: 2.4 mm overall slot length. They replace
the former 11.3 mm continuous passage. Slot allowance is for assembly correction;
tighten both joints before operation. The open root seat has Ø7.3 mm inside and
Ø10.3 mm outside diameters, giving 0.15 mm nominal radial clearance around the
Ø7 mm root. The plate is 10.3 mm wide. The 1.5 mm radial wall leaves a nominal 0.10 mm gap to the upper ear screw
withdrawal envelope; verify the finished outside surface and selected head before
assembly. This is an open locating saddle, not a
self-centring precision pilot; check actual axis alignment and gear runout.

Front nut seats remain flat, with no counterbores. The near attachment at 6.8 mm
clears the shaft boss, so the former long front relief channel is omitted.
Keep the full 1.5 mm shaft-stop floor and the existing shaft grip.

Each horn uses two **rear M1.4×8 screws and front M1.4 nuts**, without washers.
The nominal stack is 2 mm horn + 3.6 mm adapter + 1.2 mm nut = 6.8 mm, leaving
1.2 mm screw-tip projection. Require rear heads within Ø2.6 × 1 mm and front
nuts with AF 2.9–3.0 mm and height at most 1.2 mm. Actual screw heads, flat bearing
faces and drive recesses remain unmeasured. Nut limits follow the retained
[Fastenal dimensional reference](https://www.fastenal.com/content/product_specifications/M.FHN.934.A4-80.01.pdf),
not certification of the purchased brass nuts. Check physical engagement, bearing
contact, protrusion, plastic indentation and reversing-load retention.

## Assembly and service

Assemble the horn onto the servo **outside the bridge**: insert the rear screws,
fit the horn and correct OEM centre retaining screw, then add the adapter and
front nuts. The OEM centre screw is unchanged; its thread is not inferred from
the attachment screws. A rear holding-driver stem at most Ø1.5 mm and fine
pliers/open tooling at the front nuts are explicit access envelopes; verify the
actual tool tip, recess and handling space.

Insert the servo+horn+adapter unit into the bridge and secure the servo ears.
Insert the stub and gear last. For service, remove the output gears and paired
drive module, remove the selected driver gear/stub and ear fasteners, then use
the declared complete-servo withdrawal path. Off the bridge, remove the outer
front nut before the inner nut. Each nut first moves 2.6 mm forward to clear
the retained screw tip before exiting sideways. Leave rear screws in the horn
while moving the adapter 7.7 mm forward, then 40 mm outward beyond their tips.
Reverse the sequence for assembly.

The exact female spline teeth overlap the servo's smooth Ø3.9 × 2.7 mm spline
reference envelope. Validation permits that overlap only inside the uniquely
sourced cylinder; the actual case and ears remain collision obstacles. It does
not invent matching male teeth or establish physical spline fit.

Geometry checks must cover exact source-shape preservation outside the two
prepared holes, both mirrored drives, slot-end bearing support, selected hardware
seating, servo motion and the complete ordered service paths. Passing rigid CAD
checks do not establish spline fit, preload, plastic/PA12 strength, creep, fatigue,
elastic deflection or loaded gear runout.

## Superseded alternatives

The [original metal](selected_15t_4mm_horn_drawing.png),
[second metal](metal_15t_4mm_horn_6_98_drawing.png) and
[KST 0415.13 aluminium](kst_0415_13_horn_drawing.png) drawings remain historical
references. They used different holes, fasteners and an earlier universal
adapter. They are not supported substitutions for the BE adapter; do not restore
their dimensions or aluminium density into the selected plastic-horn model.
