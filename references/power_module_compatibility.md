# Optional tether and servo-power boards

Reviewed 2026-09-27 from the manufacturer pages and retained images below.
The CAD provides optional mechanical mounting capability. Battery operation stays
the default until an alternate configuration is explicitly selected and checked.
The source contract is [power_options.py](../gondola/contracts/power_options.py).

## Confirmed module data

| Module | Bare-module envelope | Input / output choices | Published current / mass |
| --- | --- | --- | --- |
| BEC12S-PRO | 35 × 24 × 5.5 mm | 9–55 V in; **one** output, 5.2 / 8 / 12 V; default 5.2 V | 5 A continuous, 9 A peak; 5 g |
| SVPDB-8S | 26 × 21 × 5 mm | 5.5–36 V in; **one** servo rail, 5 / 6 / 7.2 / 8.2 V; default 5 V | 4 A continuous, 7 A burst; 4 g |

Sources: [Matek BEC12S-PRO](https://www.mateksys.com/?portfolio=bec12s-pro),
[Matek SVPDB-8S](https://www.mateksys.com/?portfolio=svpdb-8s).
The BEC drawing abbreviates its default output as “5V”; the product text specifies
5.2 V. Both are buck converters without reverse-input protection. The BEC page
lists thermal shutdown, but does not qualify cooling or the allowed current in
this installation. Neither listed peak current is a continuous design budget.

No dedicated mechanical mounting-hole pattern is established for either board.
Their visible plated holes are electrical pads, not attachment holes. Terminal
pitch is 3.81 mm on the BEC and 2.54 mm on the SVPDB. Fitted solder, headers, plugs,
underside insulation and adhesive thickness are not included in verified mounting
datums. Do not derive a precise header height or clearance from photographs.

## Power choices and boundaries

**One BEC12S-PRO cannot supply 8 V and 5.2 V simultaneously.** For the requested
exact voltages, use two units fed independently from the 24 V source: one set to
8 V for the main input, one at 5.2 V for the servo rail. Connecting their output
positives together is not permitted. Common ground remains required.

An optional second arrangement uses one BEC at 8 V and one SVPDB at **5 V**, also
fed independently from the 24 V source. This is a different servo voltage from
5.2 V; the SVPDB does not offer a 5.2 V setting. The SVPDB can also derive its
default 5 V servo supply directly from the existing 2S battery. The CAD does not
require either optional board during ordinary battery operation.

When servo power comes from a separate regulator, disconnect servo-positive wires
from the FC 5 V rail. Keep grounds common and route each servo signal separately.
The F-Mini and other 5 V peripherals remain on their suitable supply, not the
5.2 V servo rail. Battery and tether are alternative inputs: no automatic switching,
battery charging or simultaneous battery/PSU connection is designed.

The [selected FC input-range conflict](controller_selection_review.md) applies to
an 8 V main rail as well as the existing 2S battery. The correct purchased-board
input range, regulator startup/transient behavior, installed current and cooling
remain unresolved. Nominal 24 V compatibility at the regulator does not establish
the tether's conductor rating, voltage drop, protection or entire-vehicle operation.
Switching regulators and their high-current leads near a GPS/compass require an
installed magnetic-interference check. Use another available structural host or
reroute the leads if the compass is affected; mechanical clearance is not magnetic
compatibility.

## Mechanical provision

The optional one-piece **PowerPlatform** combines a 64 × 64 × 2 mm open deck
with the common structural tower. Its complete printed height is 35 mm. Two
M2×8 screws and two ordinary M2 nuts secure its feet; no extra printed spacers,
board pockets or separate tower legs are needed. It can hold two BECs or a
BEC/SVPDB pair, while a single SVPDB leaves one bay available. The installed
battery baseline does not include this optional print, its fasteners or regulators.

The plate adds project-selected Ø2.6 mm holes on 20 and 30.5 mm square patterns,
rotated 45° to avoid the tower beam, plus tie slots beside each board bay. Those
patterns deliberately use M2 clearance; they are not a claim that all commercial
boards using those pitches take M2 screws. The two existing optical host carriers
and the accessory carrier share the structural foot interface. One carrier cannot
hold the optical tower and power tower simultaneously; move the optical tower to
the other supported optical host first. The accessory carrier is a power host,
not an additional qualified optical host.

The direct MG-F10 helix overlaps the accessory-host power platform. Use the
already allowed remote antenna installation or place the power platform on an
unoccupied battery/FC host. This is an explicit excluded combination, not a reason
to remove the antenna clearance reservation.

Use an open universal insulating support with tape/tie options. Inspect the actual
underside before fixing the board, avoid pressure on components or solder joints,
and leave the populated side exposed to air. Neither electrical solder pads nor
generic stack holes in the printed support imply a verified board bolt pattern.
Reserve accessible board ends and extra height for the chosen connection method;
these are design allowances, not measured connector envelopes.

A local tether guide is a strain-relief and routing provision only. Tie the incoming
lead to the structural carrier before the soldered board connection, keep its
free path outside moving propulsion and sensor view, and verify the installed
lead under expected pulling direction and slack. The guide does not establish a
whole-aircraft tether anchor load or a guaranteed free-hanging cable trajectory.
The deck's single tie pair locates a local attachment point. The nominal 4 mm
cable envelope extending 50 mm along local +Z is a departure allowance to check,
not a 50 mm physical guide that forces the real cable to remain straight.

The separate `gondola_power_options.FCStd`, `optional_power_mount.stl/.step`,
`gondola_power_options.json` and `gondola_power_validation.json` are generated
alongside the main CAD. The manifest identifies optional quantities and its
volume-based PA12 mass estimate. Validation checks the saved optional shapes,
main-assembly context, print exports and their identities without rewriting them.
It screens both optical-host configurations, available power hosts/plans and
navigation alternatives, including conservative seated XY/yaw registration bounds.
Permitted/rejected combinations in that current report take precedence over a
generic claim that every stack location works in every equipment arrangement.

## Retained primary evidence

Images are retained unedited from Matek. They establish nominal board size,
terminal identity and voltage selection; they do not establish mounting strength.

| Local evidence | Original source |
| --- | --- |
| [BEC12S-PRO drawing](matek_bec12s_pro_drawing.jpg) | [Matek drawing](https://www.mateksys.com/wp-content/uploads/2022/10/BEC12S-PRO_1.jpg) |
| [SVPDB-8S front/back](matek_svpdb_8s_drawing.jpg) | [Matek drawing](https://www.mateksys.com/wp-content/uploads/2022/07/SVPDB-8S_1.jpg) |
| [SVPDB output selection and typical wiring](matek_svpdb_8s_outputs.jpg) | [Matek illustration](https://www.mateksys.com/wp-content/uploads/2022/07/SVPDB-8S_5.jpg) |
| [SVPDB remote-servo wiring example](matek_svpdb_8s_wiring.jpg) | [Matek illustration](https://www.mateksys.com/wp-content/uploads/2022/07/SVPDB-8S_6.jpg) |

Manufacturer wiring examples show other flight controllers and aircraft; they are
evidence of board interfaces, not the completed wiring diagram for this gondola.
