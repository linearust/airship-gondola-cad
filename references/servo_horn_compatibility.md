# Manufacturer X06 stock half-arm coupling

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

The adapter has a **Ø1.8 mm round hole at 6.8 mm** and a **1.8 × 2.4 mm radial
slot at 13.2 mm**. The far slot's end centres are ±0.3 mm from its factory axis.
BF replaces BE's near slot with this round hole; the purchased horn, its two
prepared holes, fasteners, gear planes and shaft stay unchanged. The far slot
still accepts a nominal ±0.3 mm relative pitch error without shifting the near
joint. Tighten both joints before operation. The open root seat has Ø7.3 mm inside and
Ø10.3 mm outside diameters, giving 0.15 mm nominal radial clearance around the
Ø7 mm root. The plate is 10.3 mm wide with a 1.5 mm radial wall. Keep the ear bolts
seated during complete-servo removal as described below; do not withdraw their
heads past the assembled adapter. This is an open locating saddle, not a
self-centring precision pilot; check actual axis alignment and gear runout.

The source root outline is a rear semicircle followed by two straight tapered
edges from (X, Z) = (0, ±3.5) to (13.2, ±2.0) mm. Simply extending the circular
seat around the front intersects those edges. With BE's two slots, the adapter
could move 0.5 mm along the open-seat direction while nominal screw centres
remained fixed. The BF near round hole limits that movement to 0.2 mm. Other
directions meet the nominal root-seat boundary at about 0.15 mm. These limits
describe unclamped parts; neither the root seat nor the round hole proves
automatic concentricity. This change adds 3.888 mm³ of PA12 per adapter and
removes no material.

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

## Fit allowances and receiving checks

Keep dimensional error separate from clearance. The prepared Ø1.5 horn hole
has only 0.05 mm radial clearance around a nominal Ø1.4 screw. The Ø1.8 printed
near hole permits 0.2 mm radial screw-centre travel; the far slot permits 0.5 mm
along and 0.2 mm across the arm when considered separately. Its rounded ends do
not admit both extremes at once. The horn hole's additional 0.05 mm can increase
loose-part movement along the open-seat direction to about 0.25 mm, before
other contacts intervene. The nominal D socket has a separate 0.05 mm surface
allowance. None of these clearances is permission for motion after clamping,
or a qualified combined runout allowance.

The following are sensitivity examples for **±0.3 mm error in one stated
dimension**, not measured supplier tolerances or promises of as-printed fit.
They hold the purchased mating dimension at nominal:

| Printed dimension varied | Nominal clearance | Result at dimension −0.3 / +0.3 mm |
| --- | --- | --- |
| Near hole Ø1.8 against Ø1.4 screw | 0.20 mm radial | 0.05 / 0.35 mm radial |
| Root seat Ø7.3 against Ø7 rear root | 0.15 mm radial | 0 / 0.30 mm radial |
| Socket's round portion Ø3.1 against Ø3 rod | 0.05 mm radial | −0.10 / 0.20 mm radial; the negative value is interference |
| Adapter width/outer root diameter 10.3, upper ear head Ø3.5 at Z7 | 0.10 mm head-withdrawal gap | 0.25 / −0.05 mm gap |

If inner and outer root diameters independently vary by ±0.3 mm in opposite
directions, the nominal 1.5 mm radial wall can range from 1.2 to 1.8 mm. A
0.3 mm inward **surface-position** error is different from a 0.3 mm diameter
error: it alone exceeds the 0.15 mm root allowance. Hole position, horn shape,
seating and screw dimensions add further uncertainty. Consequently a generic
±0.3 mm print capability does not qualify this assembled interface without
finishing and inspection.

Fit a first adapter made by the final process to the received horn, screws and
rod. Finish openings toward their stated nominal sizes; do not elongate the
near round hole into a second slot. Preserve the 1.5 mm root wall and full
shaft-stop floor. Both rear heads must sit flat on the horn and both front nuts
must bear flat on the adapter, without forcing the horn or bending the shaft.
Nominal contact areas are 3.542 mm² per rear head, 5.250 mm² at the near front
nut, 4.170 mm² at the far front nut and 62.120 mm² between horn and adapter.
These are geometric areas, not load ratings. Check shaft runout through the
intended rotation while locating the assembly, then tighten the two joints and
recheck; clearance during loose assembly is not an acceptable final
eccentricity. If satisfactory fit requires removing a functional wall or
forcing parts together, rework the design or reprint.

The 0.20 mm horn-to-case gap is an assumed installed seating allowance, not
clearance created by the printed adapter. A 0.3 mm relative axial change would
consume it. The manufacturer's nominal horn and the servo envelope cannot
establish the received spline seating or OEM centre-screw stack. Verify that
the retained OEM screw seats correctly and that the horn clears the case
through the full intended input rotation. Do not hide contact by changing the
factory horn, adding an unreviewed washer or moving the gear planes.

The former separate upper-ear bolt withdrawal had only 0.10 mm nominal gap.
The current sequence avoids that path: remove the rear nuts, retain both ear
bolts in the servo and withdraw the complete unit. Fit those bolts before the
adapter during assembly. If either bolt must be removed later, detach the
adapter first on the bench. This preserves the full root wall and introduces
no new parts. The sensitivity table above records why the old path must not be
used as a manufacturing allowance.

## Assembly and service

Assemble **outside the bridge**: first place both M1.6 ear bolts in the servo
ears; insert the rear M1.4 horn screws,
fit the horn and correct OEM centre retaining screw, then add the adapter and
front nuts. The OEM centre screw is unchanged; its thread is not inferred from
the attachment screws. A rear holding-driver stem at most Ø1.5 mm and fine
pliers/open tooling at the front nuts are explicit access envelopes; verify the
actual tool tip, recess and handling space.

Insert the servo+horn+adapter+ear-bolt unit into the bridge and secure its two
rear ear nuts.
Insert the stub and gear last. For service, remove the output gears and paired
drive module, remove the selected driver gear/stub and **rear ear nuts only**,
then carry the two ear bolts through the declared complete-servo withdrawal
path. Their heads stay fixed relative to the horn and adapter. Off the bridge, remove the outer
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
adapter. They are not supported substitutions for the BF adapter; do not restore
their dimensions or aluminium density into the selected plastic-horn model.
