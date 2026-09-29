# Layout and wire management

Keep three mass regions: central propulsion, battery on one side and FC plus
other electronics on the opposite side. Battery, FC and navigation use three
identical universal carriers with independently selectable rail positions.
The paired servo/input module remains separate from the output-bearing frame.
Source [module stations](../gondola/contracts/design.py) own initial poses;
[carrier geometry](../gondola/parts/equipment_mounts.py) owns support/adhesive
datums. These are trim starting points, not a measured centre of gravity.

In neutral both main motors face +X and their rear leads face −X. Keep the FC
near those lead exits and retain its intended global orientation independently
of carrier yaw. Check the actual board arrow, firmware frame, dampers, insulation,
underbody wiring space and ESC ventilation at assembly.

The optical pitch head attaches directly to a common carrier side slot. Its
host and edge can change only with renewed combined optical, wire and service
checks. The optional power platform uses the same common slot array. Shared
holes do not establish that every populated host/edge combination works.
The radio uses the navigation carrier's opposite face beside the shoe; no
separate long branch or projecting tab is required. Tape regions must remain
fully backed by material; see the [plate interface](dense_mount_review.md).

Measured masses and lever arms must determine final trim. Neither equal spacing
nor three regions imply equal mass. Battery envelopes describe the selected
pack, not every capacity. With another pack or external supply, recheck supports,
contacts, clearances and cable/tether loads. Rail tape wings are not verified
flat electronics mounting pads.

Motor leads rotate with the carrier; servo-case leads do not. Use existing broad
members for moving-side and stationary-side strain relief, with a free flexible
transition outside rotor/gear sweeps before FC solder joints. Do not fasten to
bearings, keepers, shafts or gears, or obstruct module removal. The reserved
loop and connector corridors are workspace allowances, not actual lead-exit
datums, cut lengths, bend radii or a verified flexible harness.

Check installed leads through the entire bounded ±180° output travel, including
opposed rotor poses, tension, rubbing, twist and fatigue. Equal rigid poses at
−180°/+180° do not make the wire winding states interchangeable. Recheck after
rail adjustment; disconnect leads for the declared bare-device service paths.

Primary guidance: [MicoAir 45A installation](controller_selection_review.md)
and [igus continuous-flex cable principles](https://www.igus.com/contentData/wpck/pdf/US_en/7_guidelines_for_continuousflex_cables.pdf).
The latter does not qualify this miniature free loop. Geometry alone does not
qualify wires, adhesives, thermal operation, strength or flight readiness.
