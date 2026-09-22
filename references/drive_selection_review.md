# Drivetrain requirement and implementation status — 2026-09-22

Existing dimensions are not design constraints. Compare complete mechanisms for
this indoor LTA gondola, including couplings, retention, printability and mass.

## Selected design requirement

After reconsidering the ratio and the RC pinion candidates, the user confirmed
**metric drivetrain components only, the Notion gear ratio, and procurement
through MISUMI**.
The reviewed [Notion plan](https://app.notion.com/p/3e3ee52b5792806c94acc1f798594bad)
specifies **48T driver / 16T output, module 0.5 spur gears**. Retain that pair as
the target; do not silently substitute the previous 60T/20T pair merely because
it has the same ratio. The page's last-edited timestamp at this review was
2026-09-22T10:22:04.607Z. Its unrelated mechanical/material choices are not
automatically adopted by this ratio decision.

- Angle ratio: 3:1, with direction reversed by the external mesh.
- Reference centre distance: 16 mm for standard unshifted gears. Confirm the
  actual manufacturer's mounting distance before fixing the bridge geometry.
- Nominal servo travel of ±60° gives ±180° output. This does not compensate for
  a servo travel shortfall; ±59° would still give ±177° output.
- Gear manufacturer/SKU, bores, face widths, hubs and fixation remain unselected.
  The tooth-count decision does not select a Ø2 mm shaft or the rest of the
  Notion mechanical BOM. Select shafts, bearings and couplings together.
- Source the selected metric gears through MISUMI. Confirm complete order codes
  and Korean order availability before purchase; marketplace titles are not
  dimensional evidence. MISUMI as the purchasing channel does not by itself
  require MISUMI's own gear brand.
- Exclude the reviewed 48DP / 3.175 mm RC pinion route and inch-series supports.
  DP gears are not interchangeable with module-0.5 gears.
- Prefer lightweight parts and simple, replaceable connections. Existing CAD
  dimensions and purchased-part choices are not constraints.

## Previous CAD implementation; target conversion pending

`gondola/contracts/drive.py::SELECTED_DRIVE` and the reviewed revision AA native
assembly still implement the previous MISUMI 60T/20T pair, Ø3 shafts and MR63ZZ
bearings. The optional 64T/20T configuration is also previous implementation,
not the newly selected requirement. Existing gear purchase codes, print files,
clearance results and mass estimates do not represent a completed 48T/16T design.

Before converting CAD, obtain the actual gear drawings and establish the horn
connection, output-shaft torque transfer and axial retention. Do not extend the
existing MISUMI SKU generator to 16T while assuming its current 3 mm face,
B-type hub, bore and included set screw remain valid. Rebuild the complete axial
stack, bridge location, coupling and BOM using sourced dimensions; then audit
coupled motion, continuous clearances, assembly/service paths and the fixture
transition. The current physical fits and servo output-load capacity remain
unqualified. No directly splined X06-compatible spur gear has been verified.

## Candidate evidence, not a purchase selection

The [MISUMI GEABP catalog](https://jp.misumi-ec.com/vona2/detail/110302194440/)
includes both tooth counts in white POM with a 20° pressure angle and supplied
set screws. Its module-0.5 16T option has a K-type hub, 8 mm face width and
18 mm overall length. The 48T B-type option with 3 mm face width is 8 mm long.
This pair requires a different axial stack and clearance review; it is not a
pair of the existing thin B-type gears. Configured Korean order acceptance,
complete order codes, bores and assembled mass remain to be established.

The [KHK DS catalog](https://khkgears.net/pdf/ds.pdf) includes DS0.5-48 and
DS0.5-16 with nominal Ø5 and Ø3 bores. These differ from the previous MISUMI
interfaces. The DS bores have −0.05 to −0.30 mm deviation; no supplied set screw
is specified. KHK advises avoiding secondary machining because molded voids
may occur. A nominal bore is not proof of reliable press-fit torque or axial
retention. Both codes are listed by
[MISUMI Japan](https://jp.misumi-ec.com/vona2/detail/221004936939/); confirm a
complete simple connection and Korean purchase availability before selection.
Earlier DS0.5-48/15 and Ø2-shaft mass comparisons apply to a different mechanism
and must not be reused as a claimed saving for the selected 48T/16T requirement.
