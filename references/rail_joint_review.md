# Rail joint and fixed-frame access

Nominal CAD review; no tightening-torque, holding-force, PA12 creep, flexure-fatigue
or vehicle-load qualification is implied. Rail/shoe fit and manufacturing
acceptance remain in [rail_fit_review.md](rail_fit_review.md).

## Clamp and rail

The M2 screw tip bears on the 3 mm-high solid T head, with nominal 0.5 mm head
material above and below its full 2 mm end envelope. The opposing shoe jaw reacts
this load; the screw does not press directly on a thin tape wing. Retain complete
head lands at both clamp stations and inspect the actual screw tip for burrs.
Tighten only enough to prevent slip, then check indentation, settling and creep
under actual loads. A general-purpose screw is not a qualified pressure screw.

The lower base and tape wings are 1.5 mm thick, incorporating the user's print
review minimum. Ten identical paired wings use 36 mm pitch at X = ±18, ±54, ±90,
±126 and ±162 mm. Their 14 mm longitudinal length leaves 22 mm between wings.
They retain the continuous lower flexure and regular head lands. Default equipment
stations align with wings; the central propulsion station is bracketed by ±18 mm
wings. This geometry does not establish an acceptable balloon curvature, tape
bond or flexure life. Qualify the matched rail/shoe coupon and full rail at the
actual installed curvature with the selected PA12 process and finish.

## Fixed frame and postprocessing

The four bearing-post roots are continuous. The outboard floor is 3 mm thick;
the short central rail-service floor is 2 mm thick. The removable paired-servo
bridge retains its full coplanar central support, two outer seats and unilateral
X/Y locating faces. Route leads around the posts using existing members.

The [supplied print-review screenshot](manufacturing/frame_postprocessing_markup_2026-09-29.png) highlights small central rail-fastener
features. It does not dimension the highlighted faces; the two side-loaded nut
ports are the corresponding narrow central passages in the current geometry.
The review warns of restricted postprocessing access. It is not evidence that
this PA12 design requires printed supports in a particular process.

The fixed frame now has a 0.6 mm entrance chamfer on the top and bottom edges of
both nut-loading mouths:

| Feature | Nominal geometry |
| --- | --- |
| Port mouth before / after relief | 2.2 × 4.15 / 2.2 × 5.35 mm |
| Chamfer depth from each exterior X face | 0.6 mm |
| Retained internal throat | 2.2 × 4.15 mm |
| Remaining roof over the relieved entrance | 1.825 mm minimum |
| Minimum inner / outer lip at mouth | 1.55 / 1.85 mm, unchanged |
| Hex seat, nut reaction land, screw axis and rail capture | Unchanged |

The relief eases vertical tool approach for cleaning and finishing; it does **not**
make the whole passage wide. Work on the bare frame before installing hardware.
A nominal straight Ø2 mm finishing tip can reach the nut axis from either side,
with a Ø5 mm handle starting 3 mm outside the frame. A Ø2.4 mm tip cannot pass
the retained throat. The same Ø2 mm tip also clears nominal ±7° vertical approaches that the old
sharp mouth obstructed. These are checked tool envelopes, not identification of
Creallo's equipment or a guarantee of finishing consistency. Request confirmation
for the chosen process/finish and inspect the actual throat and received nut.

No extra part or fastener was added. The entrance reliefs remove only 1.584 mm³ of
PA12 from the frame. Exact saved-shape checks allow only these two bounded reliefs;
material removal elsewhere in the throat, rail channel or roof is still rejected.
Existing continuous nut insertion, clamp release and hex-key checks remain required.

## Assembly-tool envelope

The propulsion clamp uses a nominal 1.5 mm L-key by its short arm; equipment
clamps use its long arm. The geometric envelope reserves a 50 mm long arm,
16 mm short arm, elbow, working sector, loosening and ordered removal against
installed parts. The referenced GEDORE catalogue and product-page title have
conflicting lengths, so the model name alone is not an accepted purchase
specification; measure the received key.

The service check includes 0–2 mm socket insertion. This is an access allowance,
not evidence of the kit screw's actual socket depth. Confirm socket engagement,
key bend, hand access and wiring in the assembled vehicle.

## Source basis

- [User-supplied manufacturing feedback, 2026-09-29](manufacturing/supplier_feedback_2026-09-29.json):
  local entrance relief is the design response, not process qualification.
- [Creallo design limits](https://creallo.com/ko/guide/design-spec-guide):
  process selection and actual supplier acceptance remain pending.
- [GEDORE red catalogue, p. 66](https://www.gedore.com/-/media/files/catalogues/gedorered-catalogue-2022-2023.pdf)
  and [R36601508 product page](https://www.gedore.com/en-at/products/assembly-tools-for-screws-%2C-a-%2C-nuts/screwdrivers/cranked-allen-socket-screwdrivers-for-in-hex-screws/r3660-hexagon-socket-key-with-hexagon-socket/r36601508---3301282):
  dimensional context with the unresolved catalogue/title conflict above.
