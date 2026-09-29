# Optional tether and servo-power boards

Manufacturer data reviewed 2026-09-27; BEC/SVPDB text rechecked 2026-09-28.
Shared plate and direct-support contact regions follow the
[plate interface](dense_mount_review.md).
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
masses total **9 g**, excluding wiring, connectors, insulation and any optional support.
The two destinations share the BEC's 8 V output in parallel; the SVPDB receives
**8 V**, not the tether's 24 V. This cascade is our integration choice inferred
from the published input/output ranges, not a manufacturer-tested complete vehicle.
The BEC ships at 5.2 V: change its selection to 8 V and measure it before
connecting equipment. Leave the SVPDB at its default 5 V.

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

The user confirmed [selected-FC 2S support](controller_selection_review.md) on
2026-09-29. The 8 V main rail is nominally consistent with standard 2S operation;
no exact minimum input voltage or hardware revision is inferred. Regulator
startup/transient behavior, installed current and cooling remain unverified. Nominal 24 V compatibility at the regulator does not establish
the tether's conductor rating, voltage drop, protection or entire-vehicle operation.
Switching regulators and their high-current leads near a GPS/compass require an
installed magnetic-interference check. Use another available structural host or
reroute the leads if the compass is affected; mechanical clearance is not magnetic
compatibility.

## Mechanical packaging

**Default tether illustration: DIRECT_CARRIER.** Remove the battery and use its
existing 64 × 64 mm carrier for both regulators. Optical sensing moves to the FC
carrier. This installation adds **no printed mount or screw/nut pair**. The main
battery CAD remains a separate configuration; the optional CAD omits the battery
and shows the relocated optics. The regulator body gap, continuous
carrier contact patches, terminal/top reservations and disconnected-board removal
paths are checked in the generated report.

The two boards use nominal 1 mm insulating adhesive support on uninterrupted plate
lands, with two 12 × 4 mm strips per board. Strip centres are Y=−23, −6, +6
and +22 mm, all at X=0, clear of the middle side slots. Each board retains 96 mm² of nominal supported
contact. That allowance is not measured underside-component clearance. Inspect the
received boards, prevent conductor contact, avoid pressure on components and leave
the populated side open to air. Verify adhesive/strap retention and temperature
with the installed hardware. No electrical pad is used as a mounting hole.

Direct tether requires an optical placement compatible with the occupied battery
carrier. The saved illustration moves the optical unit to the accessory carrier's
NegativeX side. Use the generated configuration matrix for the selected optical
host, navigation/antenna and power packaging; no single host is universally
compatible. Remote antenna location and lead routing remain unmodeled. A board
fitting its carrier alone is not acceptance of the whole configuration.

**Raised alternative: PORTAL.** Battery operation with an optional SVPDB retains
the raised platform; tether can also use it where the full configuration permits.
This adds one 64 × 64 × 2 mm deck on an integral 32 mm portal, 35 mm overall, plus
two M2×8 screws and ordinary M2 nuts. The deck repeats the carriers' four fixed FC
bores, central spare bore and 24 symmetric slots. The two portal feet use opposing outer slots;
there are no board-specific holes, separate legs or added spacers. The board
centres are Y±13 mm on the raised deck. Refer to the source contract for exact
interface dimensions and the generated manifest for optional quantities/mass.

Portal registration checks cover the full opposed-slot travel and clearance,
not fictitious locating bores. Verify foot contact, actual head bearing, flatness,
clamp retention and creep. Remove its host carrier from the rail for foot-fastener
service. The bench tool check excludes only the detached rail and its tape;
the complete host, other retained obstacles, portal and boards remain checked.
Installed and registration checks still include rail and tape. With the default
P-AS accessory carrier and tether portal, the verified disconnected removal
sequence recentres the released clamp, slides 23 mm toward the negative rail end
(carrier centre X=-181 mm), then moves 32 mm away in +Z before foot service. This
rigid straight-rail check does not qualify attached wiring or installed curvature.
Power and optics cannot occupy the same host; not every carrier or
navigation configuration accepts the portal. The current report's accepted and
rejected combinations take precedence over general mounting-pattern compatibility.

Both methods use adhesive or removable straps around existing structure, with no
dedicated tie or tether holes. Secure the incoming cable before its PCB terminals
and keep it clear of rotating propulsion and sensor view. Actual cable routing,
strain relief, pull direction, thermal behavior and anchor load are unqualified.
The unchanged electrical limits above apply to either packaging method.

## Separate optional artifacts

- `gondola_power_options.FCStd`: installed direct-tether illustration, using the
  existing carrier, without the battery or a hidden installed portal.
- `gondola_power_platform.FCStd` and `optional_power_mount.stl/.step`: manufacture
  the retained PORTAL alternative only; not required for direct tether.
- `gondola_power_options.json`: separate installed and alternative manufacture
  quantities/contracts. Neither enters the main battery baseline inventory.
- `gondola_power_validation.json`: read-only saved-shape/context/metadata/export
  audit and permitted/rejected power/navigation/optical configurations.

The reports bind exact generated files and source. Nominal CAD clearance and
adhesive contact area do not qualify retention, wire handling, thermal performance
or flight operation.

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
