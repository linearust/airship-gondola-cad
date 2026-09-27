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

## Mechanical provision — purchased-adapter redesign

The optional **PowerPlatform** is one complete integral replacement carrier: its
rail shoe, lower support, portal and upper board deck are printed together. It
replaces the selected low carrier; it is not a second carrier stacked on the
first. Reuse the existing rail clamp and, at the FC host, the bought carbon and
its independent clamps. There are no separate tower feet, foot bolts, printed
spacers or extra attachment hardware. Optical and power upper structures cannot
occupy the same host simultaneously.

The current geometry authority is [power_mount.py](../gondola/parts/power_mount.py),
with common carrier geometry in
[equipment_mounts.py](../gondola/parts/equipment_mounts.py) and the integral
support construction in [stack_interface.py](../gondola/parts/stack_interface.py).
The old AX 54×74 mm deck, 20-hole template, detachable feet and seating-registration
allowances are superseded. They are historical evidence, not this installation.

The smaller upper deck is unperforated because neither Matek board has confirmed
mechanical mounting holes. Its two regions accept the BEC/SVPDB pair; one SVPDB
uses a single region. Adhesive or a removable strap around existing structure
provides attachment without dedicated tie slots or invented board holes. The
nominal insulating allowance and board separation are design allocations, not
verified backside contact, thermal separation or fitted connector dimensions.
Inspect the actual underside and leave populated faces and ventilation exposed.

The accessory variant uses straight opposed legs to clear the Mini's connector
lanes. FC and battery variants retain their own diagonal support orientation;
rotating every portal identically would conflict with lower FC hardware or its
wire reservation. Shared rail attachment does not imply identical complete
carrier geometry or universal compatibility at every station.

The accessory station is near the rail end. Its complete shoe remains engaged;
the upper deck and portal may project beyond that end. This is not a print-size
violation or an instruction to align the deck edge with the rail end. Observe the
limited outward trim described in [layout review](layout_and_wiring_review.md).
Geometric seating does not establish bending strength, creep or tether retention.

Disconnect leads and remove the whole carrier from the rail before lower-device
service. Release the relevant retention, then use the audited staged lift and
lateral path while keeping the complete integral support present. Do not assume
a device can lift vertically through the fixed upper deck. Actual soldered wires,
plugs, tools and flexible harnesses still require physical assembly checks.

The direct MG-F10 helix conflicts with the accessory-host power structure. Use
the already accepted remote-antenna arrangement or another configuration that
passes the current screen. The generated permitted/rejected combinations take
precedence over a generic claim that every mechanical host works with every
navigation, optical and power option. Do not delete a valid obstruction merely
to accept a configuration. Mechanical separation is not compass or RF clearance.

There is no dedicated tether guide, hole or certified cable trajectory. Secure
the incoming lead around suitable existing structure before its board connection,
keep the free cable outside moving propulsion and sensor view, and verify pulling
direction and slack. No aircraft-anchor load or strain-relief rating is assigned.

The separate `gondola_power_options.FCStd`, print exports, manifest and validation
report remain outside the default installed BOM. Their filenames and quantities
are defined by [power_options.py](../gondola/contracts/power_options.py).
[power_export.py](../gondola/power_export.py) checks the saved optional geometry,
main-assembly context, exports and identities without silently regenerating them.
It screens alternatives, both optical hosts, actual rail-clamp approaches and
lower-device service. Integral variants have no detachable-foot registration
freedom; old registration-float results cannot qualify them. Only reports bound
to the final matching source and saved artifacts establish a geometric pass.

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
