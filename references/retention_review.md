# Retention and assembly — AS

AS replaces the manually prepared supplied-horn coupling with a purchased
factory-threaded horn and an integral locating saddle. Output bearing retention
is unchanged from AM/AR. Source contracts and the AS revision review define the
implemented geometry and verification; older blank/jig instructions do not apply.
Nominal geometry is not qualification of received hardware, PA12 fit, friction,
spring force, creep, fatigue or strength.

## Selected replacement horn — 2026-09-25

- [AliExpress item 1005012006498403](https://www.aliexpress.com/item/1005012006498403.html),
  option **15T Single 4.0mm**, replaces the supplied horn. The saved title says
  PTK, but does not establish a manufacturer's exact SKU.
- X06 V6 compatibility is the user's accepted design premise. All three M1.6
  threaded arm holes are user-confirmed. Do not repeatedly request either
  confirmation; revisit compatibility only if concrete contrary evidence arises.
  An accepted premise is not a completed physical fit test.
- The [retained seller drawing](selected_15t_4mm_horn_drawing.png) gives overall
  length 18.2 mm, root width 6.1 mm, arm thickness 1.6 mm, first hole at 6.6 mm
  and the next interval 2.8 mm. Third-hole position 12.2 mm is inferred from
  the pictured equal pitch. The outer adapter slot accommodates +/-0.4 mm
  radial variation of that nominal position. The first two holes are too close
  for the accepted 3.5 mm screw-head envelopes on a common seating plane.
- Hub height, installed axial seating and root concentricity are not supplied.
  The 3.5 mm total height and smooth spline/OEM-head spaces are explicit CAD
  fit-prototype envelopes, not newly verified product dimensions.

## Factory-hole coupling and assembly allowance

`parts/servo_coupling.py:assembly_contract()` owns the dimensions and limitations.
The exported adapter is the installed solid, with preprinted mounting passages;
there is no separate machining blank, horn-drilling jig or horn attachment nut.

A shallow open C-saddle references the horn root. Its nominal 0.15 mm radial
clearance and 1.5 mm engagement refer to the drawn front outline, not a precision
hub tolerance. Keep the nominal axes centred before tightening; forcing the
root against one side of its clearance would introduce eccentricity. The saddle
limits rearward/lateral displacement, not automatic centring in all directions
or misalignment absorption during operation. The arm's long sides stay open.

The near clearance hole is 2.2 mm; the outer round-ended opening is 2.2 mm wide
and 3.0 mm long. These permit relative hole-position adjustment before tightening.
Both M1.6x4 screws enter the existing horn threads from the gear side, through
counterbored head seats. Nominal grip is 2.6 mm, engagement 1.4 mm and rear tip
clearance 0.2 mm. Require at least a 3.0 mm flat under-head bearing diameter
within the 3.5 mm maximum head envelope. This is a geometric acceptance, not
proven PA12 bearing strength. The outer head recess opens to the plate edge
to remove a thin rim while retaining a 1.6 mm lower end web. Actual screw length,
head, thread chamfers and aluminium thread strength still need checking. Do not
leave the screws loose to create compliance.

The nominal Ø3x18 input stub, 8 mm D socket and selected gear axial plane stay
unchanged to preserve output-shaft engagement and gear-face alignment. The former
jig passage is removed, leaving a full 1.5 mm shaft-stop floor. The M2 radial
shaft clamp and gear M3 set screw remain separate torque/retention interfaces.
The original central spline screw remains; its actual head/seat is not fabricated.

### Assembly and service

1. Fit the bought horn to X06 using its appropriate original central screw.
   Confirm actual seating against the declared axial envelope without forcing it.
2. Offer the finished adapter to the root and flat face. Use its round hole and
   outer slot to fit the factory threads, without drilling the horn or forcing
   the alignment with the screws. Dress interfering print surfaces as needed.
3. Tighten both M1.6x4 screws and fit the metal input stub and gears. Check
   engagement, thread retention, axis runout and free mesh over the permitted
   travel. The saddle and hole allowance are assembly aids, not zero-backlash
   or loaded-strength certification.
4. For front screw access, first remove both small output gears and the paired
   servo/input-drive module using its validated removal sequence. On the bench,
   withdraw the large input gear before removing the two horn screws; release
   the adapter axially, then move it clear. A straight input-gear withdrawal
   while the servo module remains in the gondola is obstructed. The source
   validation defines the full paths and retained module obstacles; actual
   set-screw tools, wiring and fingers remain physical checks.

The paired servo/input-drive module stays removable from the output frame.
Front screw access makes the old rear tool scallops unnecessary; AS restores
solid side columns in the servo bridge. The input gear still cantilevers from
the servo: physical radial-load capability has not been established.

## Output bearings: integral outer-ring capture

Four selected generic 3 x 6 x 2.5 mm ball bearings remain. Each frame cup has a
fixed outer shoulder and two releasable inboard hooks acting on the outer ring.
There are no loose bearing spacers, separate caps, cap bolts or shaft retaining
rings. The carrier's broad integral end flanges meet the frame stops; separate
shaft split clamps provide shaft grip. Neither the carrier nor a loose inner-ring
spacer is used to close the bearing retention path.

`parts/bearing_retention.py` owns the production cup, its process coupon and
the explicit release model. In each cup's local coordinates:

- The bearing occupies Y0..2.5; the hook stops at Y-0.2 and the fixed shoulder
  starts at Y2.5. Nominal bearing endplay is 0.2 mm, without preload.
- Both retaining faces have a Ø5.6 opening. Against the Ø6 outside diameter,
  this gives nominal 0.2 mm radial overlap at the outer-ring edge. The Ø5.4
  shield-clearance cylinder is a design envelope, not a measured shield.
- Two 1.5 mm-thick vertical arms have their roots below the bearing. Their
  square hooks retain the full 1.5 mm thickness without an insertion ramp;
  both arms must be held open before inserting a bearing. Open side
  pockets separate the hooks from the rigid cup. Do not fill those pockets
  when joining the cup to a frame post.
- The uninterrupted circular guide is 2.1 mm long; at the inboard travel limit,
  it overlaps the bearing by 1.9 mm. The remaining cup and two separated hook
  contacts do not imply a full circular guide through the side pockets.
- The release model moves each arm outward by 0.4 mm at bearing-centre height.
  This is a prescribed shear used for clearance checks, not an elastic model
  or a predicted hand force, permissible strain or spring lifetime.

The positive-side bearing moves 0.5 mm outward to local Y28.5..31 in the output
module, with the opposite side mirrored. The nominal Ø3 304 shaft preparations
remain 24/14/18 mm for geared-output/opposite-output/input roles respectively.
Carrier travel remains a separate nominal ±0.5 mm stop allowance. Do not infer
bearing preload or shaft grip from either axial stop.

The 0.2 mm retention overlap and endplay are smaller than general raw PA12
process variation. Print the production-matched cup coupon first, using the
agreed material, process and finish. Confirm actual ring lands, free rotation,
finished seat fit, both-hook recovery, pull-out retention, shield clearance and
repeatable release. The generic bearings are not certified ISC parts. Retained
[ISC reference dimensions](https://www.nskmicro.co.jp/products/bearing/bearing_size_pdf/single_row_mm.pdf)
are comparison evidence only.

The rejected 3 x 5 x 3 mm oil-free bush contacts the selected shield and is not
a replacement. Do not substitute a washer or make the stack longer for it.
The user's push-on ring kit is unrelated to this assembly.

### Assembly and release

Install each bearing from the empty carrier bay, holding both arms released
without loading the shield or inner ring. After seating it against the outer
shoulder, release both arms and verify their recovery and the bearing's free
rotation. Retract the separate shafts before inserting the carrier laterally;
then advance the shafts, tighten their clamps and fit the output gear. Keep
the gear/clamp flats and round bearing journals in their prescribed locations.

For bearing removal, support the rotor, remove the small gear, loosen the shaft
clamps and retract both stubs 6.5 mm. Slide the carrier 40 mm in local +X while
supporting it, then fully withdraw the stubs. Two nominal 0.6 mm
flat-blade access envelopes reach the side slots below the hooks. Hold both
arms outward while withdrawing the bearing axially. The tool shapes represent
access only; they do not establish real blade suitability or safe leverage.
Do not pry against a shield, inner ring or shaft.

Native checks must verify the retained cup material, open hook pockets,
complete hooks, guide overlap, continuous axial passage in the explicit release
pose and neighboring frame/hardware clearance. Refilled pockets or missing
hooks must fail. A passing path does not replace the process coupon or actual
assembly trial.
