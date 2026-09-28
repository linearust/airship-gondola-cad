# Selected onboard telemetry radio: LR24-F-Mini

The onboard radio is **LR24-F-Mini only**, paired with **LR24-F on the ground**.
The user's AT decision removes LR900-A support. Do not restore it as an alternate
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

## Attachment and wiring limits

AY retains the plate without a projecting landing tab. The three rail carriers
use the same 54 × 74 × 2 mm rounded rectangular plate, fixed device bores and
shared mounting slots; the revised tower feet/clamps fit inside the nominal
outline, with seating-registration limits recorded in the common interface. The accessory instance
uses the opposite plate face for the Mini, beside the rail shoe. There is no
separate radio plate, pocket, bracket or radio-specific fastening pattern.
See [universal carrier rationale](universal_carrier_review.md).

The modeled Mini is centred at accessory-local (-15, 28) mm, with its long axis
along X and its populated face directed toward local -Z, toward the balloon.
A 22 × 14 mm nominal insulating-adhesive allocation at the same centre fits
clear of the declared plate cuts and inside its edge. The body slightly overhangs the plate edge
and rounded corner; the complete adhesive allocation remains supported. This is a design
allocation, not a measured bearing face or a minimum required adhesive area.
The Mini underside photograph shows
components. Trim compliant insulating adhesive to actual supported contact and
verify component pressure, heat dissipation and retention. Velcro or ties may
wrap the existing plate without dedicated slots, keeping the populated board,
ports and antenna connection clear.

The -15 mm X shift was selected to leave rail-clamp hex-key access and separate
the connector lane from the structural foot hardware. Both rail-clamp approaches and the
structural joint's permitted seating movement must be checked; nominal body
separation alone is insufficient. The plate outline and
common mounting datums are independent of this radio placement choice. AY changes
the tower feet and generic slots, so their body, connector and tool clearances
must be checked again against the saved assembly.

The reference body occupies local Z = 4.6 to 10.4 mm, leaving a nominal 1 mm
adhesive allowance to the plate's Z = 11.4 mm face. Its connector reservations
extend toward -Z to 2.6 mm. These offsets are measured from the Z = 0 rail
reference plane, **not** from the actual balloon surface. Envelope curvature,
tape build-up, IPEX plug height, installed leads and strap pressure remain
unverified. Attach, unplug and service the Mini on the removed carrier at a
bench; this arrangement does not establish on-balloon connector access.

Preserve access at both ends of the board's X axis. Current 15 mm connector lanes
are prototype design allowances, not manufacturer connector dimensions or
verified cable bend radii. The SH sockets
and IPEX1 connector occupy opposite long-axis ends, and the IPEX1 cable mates away
from the populated face. The 2 mm design allowance beyond that face follows
the inverted installation toward -Z. Exact port XYZ and installed plug
orientation remain unmeasured. The photograph shows two SH sockets while the manual documents one
UART interface; do not infer independent UARTs or the other socket's function.

The Mini and its two end-lane reservations sit on the opposite face from the
navigation module and its conservative direct MG-F10 helix reservation. The
old same-face Y-gap argument no longer applies. Recheck the inverted body,
connector lanes, rail attachment wings and clamp seating allowance together;
the plate alone is not the complete neighboring geometry. These checks do not
verify the actual antenna seating datum, flexible pigtail or installed cables.
The optional power platform and a direct MG-F10 helix still cannot
occupy the same accessory host; use another host or the remote-antenna option.

Route and retain the flexible antenna separately, clear of the propeller sweep
and optical field. Antenna dimensions, the final mounting location and pigtail
bend limits are not established by the retained package image. No extra antenna
holder or completed harness is implied by the body envelope.

Follow the Mini's pin labels, cross TX/RX and connect common ground. The FC's
UART1/6 SH1.0-6P connection needs the corresponding verified SH1.0-4P Mini end;
connector count alone is not a pinout. The 2 W maximum-average reference does not
prove adequate shared FC 5 V BEC headroom or bound transient demand. Match the
LR24-F ground unit's communication settings and antenna. Mechanical fit does not
qualify the RF link.

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
