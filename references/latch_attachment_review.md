# Archived optical tower latch — revision AD

Historical review, superseded by revision AF. The AD/AE trial allowed nominal
0.7 mm seating play (up to 1.3 mm under its dimensional allowance). An
unspecified adhesive pad did not establish a stable optical pointing datum.
AF removes the spring fingers and guide features, directly clamping two broad
feet with ordinary M2 screws and nuts. Do not use the assembly or coupon
instructions below for the current model; current authority is
`gondola/parts/stack_interface.py` and `gondola/contracts/design.py`. All sections
below describe the AD design, including its former horn backstraps, bearing
caps and coupons; none are current purchase or assembly instructions.

The user requested structural joints in place of bolts where tightening is not
essential, while preserving simple integral parts. Two optical tower-foot
screw/nut pairs are removed. Both existing carrier locations accept the same
removable optical assembly; its two manual angle clamps remain bolted.

## Mechanism and limits

The tower has rigid support legs and feet, with one separate integral release
finger beside each leg. Each finger ends in a flat positive retaining hook.
The open slots permit powder removal and outward release without bending the
broad support feet into their seats. A single flexible leg carrying both a
hook and a broad foot was rejected: the foot rotates into the host during
release even when a translated-solid check appears clear.

The taller straight fingers reduce the geometric strain estimate without thin
hinges, extra parts or articulated latches. Actual dimensions, worst-case
clearance assumptions and strain screens are generated from
`parts/stack_interface.py`; do not maintain a second dimensional specification
here. CAD positive sensor Z points away from the balloon. Consider loading in
both directions: the hooks can carry the installed hanging load, not merely
prevent accidental separation.

The undeformed geometry has deliberate clearance. It does not establish
bolt-equivalent pointing stiffness. If the assembled tower rocks, fit a measured
piece of the adhesive consumable already required by the project at the
appropriate broad bearing faces, then check alignment again. No adhesive grade,
pad thickness, compression, preload or mass is specified from absent evidence.
The hooks must retain mechanically without the pad. Do not accept a rocking
optical sensor or assume its weight makes it self-level.

For removal, free sensor wiring and any adhesive contact, support the tower and
push it toward the carrier until the rigid feet seat and the hooks unload.
Release both hooks outward, then withdraw the complete tower while holding the
hooks clear. This is also the device-service and host-transfer path. Do not pull
the tower out while hooks remain engaged.

## Retained fasteners

| Joint | Why tightening remains necessary |
| --- | --- |
| Rail carriers | Friction holds the selected continuous trim position. |
| Output-shaft and input-stub clamps | Friction and contact transmit torque and retain the shaft. |
| Servo ears and paired drive bridge | Clamping preserves the gear-centre datum under geared loads. The paired drive module intentionally remains removable. |
| Horn-coupling backstraps | Clamping secures the bought horn after its OEM screw is installed. |
| Optical alignment pivots | Friction holds a continuously selected sensor angle. |
| Bearing caps | Controlled outer-race capture and shield clearance are sensitive to fit; adding remote spring catches would add fine geometry and tolerance risk. |

The modeled assembly removes four bought objects without adding installed
printed parts. Two mating latch coupons are test pieces only; exclude them
from the AD onboard counts and mass. Use the current `contracts/design.py`
and generated BOM for present quantities; the removed AD coupons are not
current export requirements.

## Manufacturing and physical acceptance

Use the same agreed unfilled PA12 process, finish and corresponding feature
orientation for the two mating coupons and full parts. Check dimensions,
engagement under lateral play, insertion and release, repeated disassembly,
retention under cable loads and permanent set. Reject cracks, whitening,
incomplete seating and lost retention. Test optical pointing after fitting any
anti-rattle pad. Finishing a coupon does not establish full-part stiffness or
life; repeat the relevant checks on the complete tower.

The cantilever strain equation is a geometric screen, not a PA12 allowable,
insertion force, nonlinear structural analysis or fatigue rating. Supplier
tolerance is not a geometric position tolerance or an actual-lot fit guarantee.
The project remains a fit prototype.

Source principles: [Creallo dimensional guidance](https://creallo.com/ko/guide/design-spec-guide)
supplies the dimensional screening basis; [HP joint design](https://www.hp.com/us-en/printers/3d-printers/learning-center/3d-printed-joint-design.html)
describes elastic hook assembly; [Formlabs snap-fit guidance](https://formlabs.com/blog/designing-3d-printed-snap-fit-enclosures/)
supports gradual roots, longer flexures and physical fit iteration. These sources
do not qualify this particular hook geometry or the selected manufacturing lot.

## CAD verification

The reviewed AD assembly passes 259 native FreeCAD tests, saved assembly and
equipment validation on both optical hosts, and comparison of all 126 shape
objects and native controls against the audited AD fixture. Print exports and
the prototype archive pass source/CAD identity and inventory checks. See
`tests/fixtures/rev_ad_review.json` for the intentional AC-to-AD changes.
These results verify modeled geometry and consistency, not the physical
acceptance requirements above.
