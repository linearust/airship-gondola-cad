# Interchangeable navigation modules

Reviewed 2026-09-25 for AT. The user selected one shared navigation location for
**LinkTrack P-AS, MicoAir MG-A01/M10 Ultra, or MG-F10 with an external helix**.
These are alternatives, not three simultaneously installed devices. P-AS remains
the default until a specific GPS is selected. Mechanical interchangeability does
not make their protocols, compass settings or installed antenna clearances equal.

## Verified GPS interfaces

| Item | MG-A01 / M10 Ultra | MG-F10 / bare MG-F10-A |
| --- | --- | --- |
| Module envelope | 25 × 25 × 8 mm | 34 × 22 × 13.4 mm, including SMA socket and underside projection |
| Published module mass | 12 g | 6 g without helix |
| Antenna | Integral 25 × 25 × 4 mm patch | Separate SMA quad helix, Ø28 × 59.3 mm, 15 g |
| Mounting holes | No confirmed hole pattern | Four Ø2 mm holes, 28 × 16 mm pitch |
| Signal connector | SH1.0-6P on one edge | SH1.0-6P on a short edge |
| Interface | 5 V; UART GPS and I²C compass | 5 V; UART GPS and I²C compass |

The [MG-A01 product page](https://micoair.com/gps_mg-a01/) explicitly identifies
M10 Ultra as MG-A01. It gives 7.8 mm thickness; the current
[GPS manual](https://micoair.cn/zh/docs/gps-rtk/gps) and its dimension drawing give
8 mm. Use the larger 8 mm nominal envelope. Do not substitute the smaller
20 × 20 mm M10G-5883 or assume an unverified enclosure is included.

The [MG-F10 product page](https://micoair.com/mg-f10/) and
[MG-F10-A manual](https://micoair.cn/zh/docs/gps-rtk/mg-f10/mg-f10-a-gnss) describe
the bare module and external helix above. The **MG-F10-C** is a separate enclosed
product; its housing dimensions and GH connectors are not this interface.

## Attachment and antenna limits

Use a generic insulating adhesive support rather than reproducing the GPS holes
or adding another bracket merely because one model has holes. Retain the P-AS
mounting axes for its selected installation. Check the actual GPS rear contact
surface before applying tape: the MG-F10-A drawing shows SMA solder projections
under the board, and MG-A01 has components and shielding opposite its patch.
A nominal rectangular equipment envelope is not evidence of a flat adhesive
face. Foam, an insulating pad or locally relieved tape must not press on fragile
components or obstruct the signal connector. No adhesive strength, compressed
tape height or complete contact footprint is certified by these drawings.

MG-F10's helix is **additional equipment**, not part of the 13.4 mm module height.
Reserve space for it and for SMA handling. The sources do not dimension the
SMA-axis XY datum or the assembled antenna seating plane. Do not recover those
dimensions by scaling photographs, or mark a guessed exact antenna position as
verified. A conservative swept envelope over possible SMA positions is acceptable
for preliminary interference screening if clearly identified as a design reserve.
Final antenna seating, connector access and attachment stability require the
actual module. Supporting only the PCB does not establish that its tape joint
can carry a tall 15 g antenna or connector-tightening loads.

## Shared carrier and antenna arrangements

AT replaces the long shared FC/navigation arm with one plain rail-mounted
accessory plate for the selected navigation module and the onboard Mini radio.
The plate includes the two confirmed P-AS mounting axes. GPS alternatives use
an unpierced 18 × 14 mm adhesive allocation in the same navigation region; the
P-AS holes lie outside this rectangle. These are mutually exclusive devices.
The FC retains its own compact carrier and optical-stack anchors.

The accessory plate's offset rail shoe places the navigation region outward
from the FC. This spacing retains the conservative direct-helix reservation and
both optical hosts; it is not arbitrary excess length. Moving the plate inward
requires renewed optical, antenna, connector and service clearance checks.
The 2 mm plain deck is supported directly by its integral shoe without a long
narrow navigation branch. Loaded deflection and tape retention, especially with
the 15 g helix, still require a prototype. Support the SMA socket while attaching
its antenna; do not use the printed deck as a tightening lever.

The user accepts both MG-F10 arrangements:

- **Direct attachment:** reserve the complete possible antenna location above
  the module, including its unknown seating depth. The nominal bound spans the
  module footprint plus the helix radius on every side. This is clearance
  geometry, not the antenna's actual centre or a manufactured antenna mount.
  Remove the helix before servicing the adjacent SH connector if necessary;
  the exact simultaneous plug/antenna fit remains unmeasured.
- **Separated antenna:** use a suitable SMA extension and secure the helix
  independently with its receiving direction toward the sky and an unobstructed
  view. Actual extension connector sex, length, RF loss, strain relief and
  antenna attachment must be selected for the received module and airframe.
  No antenna position or support on the unmodeled envelope is invented.

CAD +Z points away from the balloon and downward in the installed gondola. A
direct helix extending from the modeled upper module face consequently points
downward, so direct-attachment mechanical screening does **not** establish a
suitable outdoor GNSS installation. The separated upward-facing arrangement is
the intended option when outdoor GNSS reception matters. MG-A01's integral patch
cannot be separated in the same manner: its tape mounting is mechanically
accommodated, but the actual sky-facing orientation, envelope obstruction and
RF performance must be resolved on the vehicle. Neither GPS option is declared
flight-qualified merely because its body fits.

Keep the patch or helix oriented for reception and leave it uncovered by other
equipment. Follow the selected module's compass orientation. MicoAir's MG-A01
instructions say to keep the module away from power-output wiring; a CAD gap
alone cannot certify magnetometer or RF performance. The shared location does
not establish indoor GNSS availability or authorize a change from P-AS firmware
and UART settings without corresponding integration checks.

## Retained primary evidence

The original manufacturer images are retained without dimension inference.

| Local file | Original source |
| --- | --- |
| [mgf10a_dimensions.png](mgf10a_dimensions.png) | [Bare module, hole pattern, helix and masses](https://micoair.cn/api/media/file/docs/2026/07/670a2bdd48e84-5d41a070a6.png) |
| [mgf10a_ports.png](mgf10a_ports.png) | [MG-F10-A SH1.0-6P, SMA and forward arrow](https://micoair.cn/api/media/file/docs/2026/07/670a2cf93e54a-f112ee7037.png) |
| [micoair_gps_dimensions.webp](micoair_gps_dimensions.webp) | [GPS family dimensions; MG-A01 is the left column](https://micoair.cn/api/media/file/docs/2026/07/66a20fad7f8af-b764097238-3c14051a33.webp) |
| [micoair_gps_ports.webp](micoair_gps_ports.webp) | [GPS family rear faces and SH1.0-6P; MG-A01 is bottom right](https://micoair.cn/api/media/file/docs/2026/07/66a21138a03b7-e888424f70-9252767bfd.webp) |

These are interface inputs and limits. Geometric results belong to the generated
validation reports for the saved assembly and selected navigation profile.
