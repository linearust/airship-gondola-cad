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
- Both purchased gears must have **nominal Ø3 mm bores**. This user requirement
  supersedes the nominal Ø2 mm bores in the reviewed Notion gear rows; it is not
  permission to resize a different catalog bore in CAD or machine a bought gear.
- Gear manufacturer/SKU, face widths, hubs and fixation remain unselected.
  Select shafts, bearing fits and couplings together; a nominal Ø3 mm bore alone
  does not establish fit tolerance or retention.
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
The previous driver gear and its printed coupling use a Ø7 mm bore. The selected
Ø3 mm driver requires a new verified horn-to-gear connection; do not simply
shrink that coupling's hollow post or assume the plain bore fits the X06 spline.

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
Both tooth counts offer a nominal Ø3 mm bore in the catalog.
This pair requires a different axial stack and clearance review; it is not a
pair of the existing thin B-type gears. Configured Korean order acceptance,
complete order codes, the final axial dimensions and assembled mass remain to
be established.

The previously reviewed [KHK DS pair](https://khkgears.net/pdf/ds.pdf) is excluded
from this target: DS0.5-48 has a nominal Ø5 mm bore, so pairing it with the Ø3 mm
DS0.5-16 does not meet the requirement for two Ø3 mm bores.
