# Retention and assembly — AM

This describes the AM geometry after the native old/new audit, validation and
regression checks, with the matching build/preview/compare/bundle pipeline
complete. Generated artifacts carry the CAD hash and source
fingerprint. AL exports and inspection instructions do not describe the changed
bearing and horn interfaces.
Nominal geometry is not qualification of received hardware, PA12 fit, friction,
spring force, creep, fatigue or strength.

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

## Supplied X06 horn and prepared adapter

Use the horn supplied with the selected X06 and its original central screw.
There is no separate KST 0415.13 purchase or inherited tip-hole modification.
The supplied horn's outline, material, holes and axial seating are unmeasured.
Its model is an illustrative prepared specimen; it is not a purchased drawing.

The printable adapter is an undrilled machining blank. The assembly's two-hole,
faced adapter is only the prepared example. Export `PrintBlankShape` for the
adapter and retain the native prepared shape for assembly-motion checks. The
centering jig is a separate temporary bench coupon, removed before installing
the metal input stub; it is not flight hardware or an added input bearing.

`parts/servo_coupling.py:machining_contract()` defines the current working
envelope and the example separately. Its facing range retains at least 3 mm of
plate in the horn-contact area outside the central hole and hub relief. The
perforated socket-stop floor is a separate 1.5 mm feature, not a 3 mm plate
measurement. Horn-local Y0 lies 0.2 mm gearward of the servo-case front face;
do not substitute the horn back face as that datum. Actual arm thickness must
also leave clearance for both rear Phillips heads. The near hole is fitted closely to the measured M1.6 shank; Ø1.7 is the
CAD example, not a delivered tolerance. The second Ø1.8 example hole provides
assembly allowance. Neither clearance hole proves concentricity, zero backlash
or sufficient torque capacity. If the measured horn lacks two sound fastening
sites, revise the blank rather than cutting into its spline/root or an existing
hole. Arbitrary arm and round-disc compatibility is not claimed. The machining
area is not a service-clearance certification over every possible hole location:
locations other than the checked X8/X12 example require renewed collision and
tool/removal-path checks.

### Workshop preparation and service

1. On an unpowered bench, inspect the genuine horn and its installed seating.
   Temporarily remove only its OEM central screw. Face the blank to the actual
   arm while preserving the gear seating datum and socket-stop floor.
2. Finish the jig's D guide to the same socket. Lightly seat its soft conical
   nose on a measured, circular screw-entry feature concentric with the output.
   Do not force the nose into threads. The small printed tip is a prototype:
   supplier agreement, finishing, seating and damage inspection are required.
3. Hold the centered horn/blank relationship with temporary bench clamps and
   transfer two suitable hole locations. Remove the parts from the servo while
   preserving that registration in the fixture. Drill the supported pair,
   deburr and clean away chips; never drill into the servo.
4. Remove the adapter/jig and reinstall the genuine horn with its OEM central
   screw. Attach the prepared adapter with both rear M1.6 screws and front nuts.
   Remove the jig permanently before fitting the input stub and gear.
5. Check actual stub/gear runout through the permitted motion without forcing
   the servo's internal gear train.
   Align before final tightening and check mesh, both torque directions and
   drift again. No numerical runout, torque, creep or fatigue acceptance has
   been qualified by this CAD exercise.

For adapter removal, withdraw the small output gear first. Fully remove the
Far nut, then its bolt, before fully removing the Near nut and then its bolt.
The next pair remains installed until the preceding pair is removed. For
central-screw service, remove the input gear, metal stub and adapter as required
before using the proper tool on the original screw. The axial guide opening
serves the jig stem; it is not a claim that an unknown OEM screw head can be
inserted through the finished socket. No side-insertion shortcut is assumed.

The input remains a nominal Ø3 x 18 mm 304 stub with a full-length flat, retained
by the adapter's radial M2 clamp facing horn-local negative Z and the gear's
actual M3 set screw. Preserve
separate axial retention and torque transfer. Geometry checks of the example
do not certify the user's unmeasured horn, drilling setup or finished coupling.
