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

The selected optional tether arrangement is:

```text
24 V PSU -> BEC12S-PRO set to 8 V -> FC VBAT / propulsion input
                                -> SVPDB-8S input -> 5 V servo-positive rail
```

Purchase **one BEC12S-PRO and one SVPDB-8S** for this option: the published board
masses total **9 g**, excluding wiring, connectors, insulation and the platform.
The two destinations share the BEC's 8 V output in parallel; the SVPDB receives
**8 V**, not the tether's 24 V. This cascade is our integration choice inferred
from the published input/output ranges, not a manufacturer-tested complete vehicle.
The BEC ships at 5.2 V: change its selection to 8 V and measure it before
connecting equipment. Leave the SVPDB at its default 5 V. Earlier advice requiring
two BEC12S-PRO boards assumed an exact 5.2 V servo rail; that assumption is no
longer part of the design. No second BEC12S-PRO is required for these selected rails.

The BEC's published **5 A at 8 V is shared by all main loads and the SVPDB input**.
The SVPDB's 4 A rating is at its own output; it does not add another 4 A to the
8 V supply. At positive load, with `eta` the SVPDB's total conversion efficiency:

```text
I_BEC_8V = I_main_8V + (5 V * I_servo_5V) / (8 V * eta)
```

No measured `eta` is assigned. If the servo rail supplies its catalog 4 A, that
is 20 W, requiring **more than 2.5 A at 8 V** after losses. Thus **less than 2.5 A**
of the upstream catalog limit remains for main loads, even before installation
derating or reserve. These are power-balance limits, not measured motor demand.
The 9 A/7 A peak figures are not a continuous or guaranteed simultaneous budget.
Measure combined startup/stall transients, voltage sag and heating before accepting
the installed supply. A servo overload can disturb the common 8 V rail and FC.

For battery operation, one optional SVPDB may instead take its input directly from
the existing 2S battery and supply servos at 5 V. Basic battery operation still
adds neither optional board to the installed inventory. No hardware modification
can be inferred from merely viewing the separate optional CAD.

When servo power comes from a separate regulator, disconnect servo-positive wires
from the FC 5 V rail. Keep grounds common and route each servo signal separately.
The F-Mini and other peripherals remain on the FC's appropriate supply. Never join
the FC and SVPDB 5 V output positives, despite their matching nominal voltages.
Battery and tether are alternative inputs: no automatic switching,
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

The optional one-piece **PowerPlatform** combines the common **64 × 64 × 2 mm**
rounded square deck with a diagonal portal. The deck has the same 3 mm corner
radius and symmetric mounting array as every rail carrier. The portal remains
32 mm high above its host seating plane; the complete optional print is 35 mm
high. Its two 13 × 9 × 2 mm feet remain inside the square outline, with a 5 mm
inward corner relief that leaves the diagonal leg roots intact. Two M2×8 screws
and two ordinary M2 nuts secure the feet; there are no extra printed spacers,
board pockets or separate legs. The BEC/SVPDB board regions remain centred at
Y = ±13 mm, giving the selected bare pair a nominal 3.5 mm body gap. This is an
envelope allocation, not tested cooling or a completed harness. None of this
optional print, its four fasteners or the regulators enters the battery baseline.

The deck shares the carriers' **four fixed FC bores and sixteen slots**:
four M2 diagonal slots for 16–23 mm square pitches, four M3 arcs for a 30.5 mm
square, and eight outer M2 slots. See
[mounting_slots.py](../gondola/parts/mounting_slots.py) and
[equipment_mounts.py](../gondola/parts/equipment_mounts.py).
The P-AS uses two endpoints of the shared 23 mm diagonal pattern. The optional
portal feet clamp through common outer slots at nominal local (+27,+23) and
(−27,−23) mm; no separate structural carrier bores are added. These provisions
are not either Matek board's mounting holes. Slots crossing the top beam cut
through the fused support beneath the deck. Existing small M2 heads are not
qualified for the wider M3 slots; no baseline washers are added.

The foot holes are circular while their host openings are slots. The geometric
registration bound therefore includes the **full opposed-slot travel** and the
combined clearance of both printed interfaces. It does not treat the host as
having two locating bores. Seat the feet and centre the portal before tightening.
Underside heads bear on the two sides of a slot: actual head diameter, seating,
print flatness, clamp retention and PA12 creep still require inspection/testing.
The saved audit checks actual material under both nominal foot seats, clear screw
paths and geometric access to their fasteners. Remove the carrier from the rail
for foot-fastener service; balloon clearance is not modeled.

The battery, FC and accessory carriers share this optional portal attachment.
The optical head now uses a separate compact one-axis pedestal rather than the
same portal. Concurrent optical and power installation on one host remains
excluded; move the optical head to its other supported host first. Matching
slots alone do not establish clearance, module access or structural capacity.
The previous AY host-screen results belong to the earlier rectangular plate and
two-axis optical tower. Current square-carrier/one-axis combinations must pass
the generated configuration screen. In particular, do not assume that a direct
MG-F10 helix or a propulsion-adjacent FC carrier accepts the power platform;
use only a currently permitted host/antenna combination.

Dedicated board tie slots, tabs and tether holes are absent; adhesive or a
removable strap around existing structure provides simple attachment options.

Use the open insulating support with suitable adhesive or a removable strap. Inspect the actual
underside before fixing the board, avoid pressure on components or solder joints,
and leave the populated side exposed to air. Neither electrical solder pads nor
generic stack holes in the printed support imply a verified board bolt pattern.
Reserve accessible board ends and extra height for the chosen connection method;
these are design allowances, not measured connector envelopes.

There is no dedicated tether guide, retention hole or modeled cable trajectory.
Secure the incoming lead around suitable existing structure before its soldered
board connection, keep its free path outside moving propulsion and sensor view,
and verify pulling direction and slack after installation. The CAD does not
establish tether clearance, an aircraft anchor load or a strain-relief rating.

The separate `gondola_power_options.FCStd`, `optional_power_mount.stl/.step`,
`gondola_power_options.json` and `gondola_power_validation.json` are generated
alongside the main CAD. The manifest identifies optional quantities and its
volume-based PA12 mass estimate. Validation checks the saved optional shapes,
main-assembly context, print exports and their identities without rewriting them.
It screens both optical-host configurations, available power hosts/plans and
navigation alternatives, including conservative seated XY/yaw registration bounds.
The square carrier and compact optical pedestal require renewed checks; historical
AY successes are not current qualification. A complete screen requires at least
one permitted host for each optional power plan. The separately saved illustration
must also be clear on its actual default host. Moving the optical head may change
which power host is permitted; it does not require every host combination to work.
Permitted/rejected combinations in the current report take precedence over a
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
