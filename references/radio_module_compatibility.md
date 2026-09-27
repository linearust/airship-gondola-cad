# Selected onboard telemetry radio: LR24-F-Mini

The onboard radio is **LR24-F-Mini only**, paired with **LR24-F on the ground**.
The selected scope excludes LR900-A. Do not restore it as an alternate
profile, add a full-size F bracket, or count the ground unit as onboard mass.

## Manufacturer interface

| Item | LR24-F-Mini design input |
| --- | --- |
| Body envelope, long side × width × height | 24 × 18.2 × 5.8 mm, excluding external antenna/pigtail |
| Published module mass | 2.5 g; actual installed mass unmeasured |
| UART connector | SH1.0-4P |
| USB | None; use a 3.3 V logic USB–UART adapter for setup |
| Antenna connector | IPEX1; flexible external T-antenna pictured in package |
| Supply / UART logic | 4.5–5 V / 3.3 V |
| Maximum average power reference | 2 W; calculated 0.40 A at 5 V, not a peak-current limit |

Sources: manufacturer [LR24 manual](https://micoair.cn/zh/docs/telemetry/lr24/lr24-telemetry),
[store specifications](https://store.micoair.com/wp-content/uploads/2025/01/LR24_params.webp)
and [dimension drawing](https://store.micoair.com/wp-content/uploads/2025/01/LR24_size.webp).
The Mini height and IPEX1 identification come from the store table and side view;
the manual's general SMA statement does not describe the bare Mini board.
Published module mass excludes the separately fitted antenna, harness and adhesive.

## Attachment and wiring limits — current design

The Mini shares one compact insulating accessory carrier with the selected
navigation module. Both occupy the outer face, away from the rail and balloon;
there is no separate radio plate, projecting tab, pocket or radio-specific bolt
pattern. Current body placement, adhesive allocation and carrier geometry belong
to [equipment_layout.py](../gondola/parts/equipment_layout.py) and
[equipment_mounts.py](../gondola/parts/equipment_mounts.py). The Mini and navigation
occupy opposite ends of that face, with separate connector reservations.

The previous AX identical 54×74 mm carriers, inverted Mini at (-15,28),
underside Z offsets and stack-foot clearance argument are superseded. They do
not describe the current installation. The shared interface is now the rail
coupling, not a requirement that all role carriers have identical decks.

A continuous nominal insulating-adhesive allocation supports the Mini. Its
underside photograph shows components: trim compliant adhesive to the actual
contact, avoiding pressure on solder, components and the antenna connector.
The modeled body and supported patch do not qualify contact area, heat dissipation
or retention. Velcro or ties can wrap existing structure without dedicated slots.
Keep the populated face, sockets and antenna connection accessible.

Preserve clearance at both ends of the Mini's long axis. The current end lanes
and allowance above the populated face are prototype design reservations, not
manufacturer connector dimensions or measured cable bend radii. The SH sockets
and IPEX1 connector lie at opposite ends; the cable mates away from the populated
face. Exact port XYZ, installed plug height and final wire direction remain
unmeasured. Two photographed SH sockets do not establish independent UARTs or
the function of an undocumented socket.

For the low carrier, bare-device removal is outward from the same outer face
after disconnecting leads and releasing adhesive/retention. Retain other mounted
parts in that interference check. The optional integral power variant has a fixed
upper deck, so its lower radio requires the separate detached-carrier lateral
service path. Neither path certifies a connected harness or practical hand access.
Inspect the actual installation instead of inferring access from a body-only gap.

The current source screens navigation alternatives, both connector ends, rail
clamps, propulsion and optical fields together. The accessory-host power variant
uses a different portal orientation to preserve the Mini lanes. A direct MG-F10
helix and that power structure still conflict; use a permitted alternative or
remote antenna. Consult the matching power and equipment reports after changes.

Route and retain the flexible radio antenna separately, clear of propellers and
sensor view. Its final mounting location, pigtail bend limits and installed
connector datum are not established by the package photograph. No extra antenna
holder or completed harness is implied by the reference body.

Follow the Mini's pin labels, cross TX/RX and connect common ground. The FC's
UART1/6 SH1.0-6P connection needs the verified SH1.0-4P Mini end; connector count
alone is not a pinout. The 2 W maximum-average reference does not prove shared
FC 5 V headroom or bound transient demand. Match the ground LR24-F settings and
antenna. Mechanical fit does not qualify electrical capacity or the RF link.

## Retained primary evidence

Manufacturer evidence checked 2026-09-24; selection narrowed to the Mini on
2026-09-25. These images are retained unedited.

| Local file | Original source |
| --- | --- |
| [lr24_specifications.webp](lr24_specifications.webp) | [Mini model, dimensions, IPEX1 and electrical data](https://store.micoair.com/wp-content/uploads/2025/01/LR24_params.webp) |
| [lr24_dimensions.webp](lr24_dimensions.webp) | [Mini plan and side view, including 5.8 mm height](https://store.micoair.com/wp-content/uploads/2025/01/LR24_size.webp) |
| [lr24f_mini_ports.webp](lr24f_mini_ports.webp) | [SH1.0-4P connector and pin labels](https://micoair.cn/api/media/file/docs/2026/07/66a0c156834c9-2fc5d7c4ba-76f5fe2816.webp) |
| [lr24f_mini_package.webp](lr24f_mini_package.webp) | [F ground + Mini air package and external T-antenna](https://store.micoair.com/wp-content/uploads/2025/01/LR24FFmini_package.webp) |

Full-size F dimensions and mass differ between the manual drawing and current
store table. This does not affect the Mini onboard envelope: the F is ground
equipment and has no fitted CAD interface here. Do not substitute its drawing
for the Mini.
