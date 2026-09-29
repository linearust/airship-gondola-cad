# Denser symmetric common mounting plate

Current design update, 2026-09-29. The shared 64 × 64 × 2 mm plate gains mounting
positions along its side midpoints and outer diagonals. These are usable geometric
adjustments, not a claim that every device or occupied configuration fits. The
[BB review](square_mount_review.md) and its verification remain historical.

## Openings and retained structure

All coordinates below are local to the plate. The complete opening array retains
quarter-turn and X/Y mirror symmetry. The rail shoe remains directional.

| Family | Current geometry |
| --- | --- |
| FC | Four unchanged Ø2.6 mm fixed bores, 25.5 mm square at 45°; complete Ø6.5 mm bearing annuli |
| Inner diagonal | Four unchanged 2.6 mm slots covering axis-aligned square pitches 16–23 mm; shifted P-AS uses its existing two endpoints |
| Larger square | Four unchanged 3.6 mm arcs for a 30.5 mm square at ±15° |
| Side | Twelve 2.6 mm slots on X=±27 or Y=±27; centre travel −23…−13, −5…5 and 13…23 mm on each side |
| Outer diagonal | Four new 2.6 mm slots from (20,20) to (22.5,22.5) and quarter-turn copies, covering 40–45 mm square pitches |

There are four fixed bores and 24 slots. The middle side slots expand the general
cross pattern; the separately designed centreline optical support and raised
power feet use reviewed positions in the outer intervals. Neither interface
requires dedicated extra carrier holes. The outer
diagonal ends stop at 22.5 mm rather than joining the side slots: their nearest
opening-to-opening web is 1.9 mm. All slots retain at least 1.5 mm of continuous
material through the full plate thickness, including curved edges and end caps.

The plate outline, corner radius, FC/P-AS datums, Z=13.4 mm underside, Z=15.4 mm
support face, full Ø17 mm central support and integral rail shoe are unchanged.
The central support is not perforated to fill the centre with an extra pattern.
The three equipment carriers remain one physical print used in three roles;
the optional power deck uses the same plate template.

The native shape checks cover complete screw-head and shank sweeps along every
M2 slot, including the new positions, against the actual support/shoe and rail in
both lateral clamp poses. They also retain both rail-key approaches and the nut
loading/release paths. This does not qualify arbitrary installed boards, screw
heads or loads. The selected small M2 heads are not approved for the M3 arcs.

## Contact allocations

The mandatory middle slots intersect the old battery end patches and radio
patch. Their declared contact regions therefore change along with the openings;
passing a hole check while leaving unsupported tape allocations is not accepted.

| Device | New continuous supported patches | Nominal area |
| --- | --- | --- |
| Battery | 12 × 18 mm at (0,0), plus 16 × 5 mm at (0,±22.5) | 376 mm², down from 536 mm² |
| Mini radio | 4 × 15 mm at (23,−7.5), plus 3 × 20 mm at (30,−11), on the underside | 120 mm², unchanged total |
| GPS alternatives | Unchanged 12 × 14 mm at (0,−2.2) | 168 mm² |

The two radio strips lie on opposite sides of the side-slot row. Each retains
60 mm² of complete carrier backing and nominal body overlap, with the existing
1 mm insulating-adhesive allowance. The radio body at (26,−11), its orientation,
connector reservations and removal direction remain unchanged. No extra printed
pad, fastener, spacer or support part is added. Tests remove material independently
under every declared strip and reject partial body overlap and the wrong contact
face. The battery end patches move inward to avoid the new transverse slots.

These areas describe available material, not qualified holding strength or a
measured component-free PCB underside. Inspect the actual radio underside before
choosing insulation and applying narrow strips. Verify battery retention with the
reduced contact allocation; shifted packs may cover less. Do not treat equal
radio area as proof of equal peel resistance, strength, cooling or durability.
The separate direct-power contract defines its own supported adhesive regions.

## Verification boundary

Plate tests retain exact full-opening/full-land checks, fixed-bore annuli, both
mirror symmetries, whole-path head clearance, unchanged central-support material
and independent missing-material/blocked-opening mutations. New diagonal and
middle-side slots are included in the negative tests. Source metadata lists all
slot families and individual radio strips rather than a stale fixed slot count
or a single contact rectangle.

The final release evidence must also check installed optical/power feet, their
tools and removal paths, all supported sensor/navigation combinations, saved CAD
and exports. This note does not claim that those broader checks have already
passed. Removing material preserves the stated geometric margins; actual plate
stiffness, PA12 strength and creep, adhesive retention and loaded assembly behaviour
remain physical qualification work.
