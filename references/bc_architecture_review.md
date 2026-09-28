# BC architecture review

This revision changes the removable servo-module joint and the optional tether
installation. The battery baseline, bought gears/shafts/bearings, gear axes,
independent tilt, rail and three common equipment carriers remain the design basis.
The paired servo/input module remains separate from the output-bearing frame.

## One support plane for the removable drive module

The previous joint seated its two outer feet at Z8.7 mm and its central support
at Z11.4 mm. Drawing all three faces into contact depended on two printed step
heights as well as flatness. The revised joint puts all three support regions at
Z11.4 mm. The bridge has one flat 2 mm plate instead of downward pads and head
counterbores; the frame's outer seats rise to meet it. The existing two M2×8 pairs
keep their 5 mm grip. Unilateral X/Y datums locate the module; bolts clamp it.

This simplifies the locating/load interface without moving either servo or gear
axis, changing the ratio, adding parts, or relying on loose running fits. The
common plane still needs flatness and simultaneous seating. Do not pull a warped
part into contact with the screws. Creallo publishes SLS/MJF tolerances of ±0.3%
with a ±0.3 mm minimum; nominal contact in CAD is not an as-printed fit guarantee.
[Supplier dimensional guide](https://creallo.com/ko/guide/design-spec-guide).

Validate the central and each outer seat within separate XY regions, not one
summed contact area: otherwise a large central contact could mask a missing outer
support. Also check locating faces, screw/nut engagement, tool access and the
complete ordered module-removal path. The independently compared saved solids
reduce combined frame/bridge volume by 284.719 mm³, about 0.288 g at the
provisional PA12 density; this is an estimate, not a measured mass reduction.

## Optional tether packaging

Tether power replaces the flight battery. Its two regulators can use the vacated
battery carrier instead of adding a tall platform above navigation. Keep this
configuration distinct from battery operation with an optional servo regulator.
Each board uses two separated 12 × 4 mm adhesive regions on existing central/end
lands; board centres at Y±14 mm leave 5.5 mm between bare bodies. The directly
mounted boards need insulating compliant support and real lead/strap routing; plated electrical pads are not mechanical mounting holes.

The retained raised platform remains available for battery/SVPDB operation and
other permitted combinations; it is not installed in the direct-tether example.
The optional native installation, exports, quantities and configuration screen
must agree on what is installed. Optical host and navigation choice must be checked
together with power packaging: a power-only clearance result must not mark an
already obstructed optical/navigation combination as permitted.

## Alternatives considered

- **Flip both gear hubs and slide the paired module sideways with all gears
  retained:** static fit works, but the release path strikes the inner bearing
  cup/post. Flipping shifts the input tooth band 5 mm toward its servo, reducing the
  tooth-band distance from the modeled horn seating plane from 21.6 to 16.6 mm,
  while increasing output overhang
  from 6.75 to 11.75 mm. Avoid modifying bearing support and increasing output
  bending just to eliminate two gear-removal operations. Keep the checked sequence:
  remove the small gears, release the two mounting pairs, lift and slide the module.
- **Stiffen the output feet with ribs:** a section-only stiffness gain would not
  address the narrower central floor's compliance. Loads and assembled deflection
  are unmeasured. Do not add complicated ribs and disturb access without evidence.
- **Merge or aggressively thin the equipment carriers:** preserve the three mass
  regions, common square interface and independent rail trim. Received FC damping/
  fastening stacks, adhesive retention and wiring remain more important unresolved
  details than a small modeled volume saving.
- **Lift the battery past installed optics:** a straight lift clears the nominal
  MTF-02P in the sampled poses, but intersects MTF-01P at −20° pitch. Retain the
  documented optical-removal prerequisite until a complete alternative path is
  established for both sensors and allowed placements.

## Limits

These decisions improve nominal packaging and assembly architecture, not physical
qualification. PA12 flatness/creep, X06 radial capacity, horn seating/runout,
bearing fits and shield contact, actual fasteners, adhesive/insulation, cable
bends/tether loads, installed thermal behavior and FC input compatibility remain
open. Do not infer strength, service force or flight readiness from collision tests.

Exact generated-file verification and the independent geometry-transition review
are recorded separately; historical BB records describe BB, not this revision.
