# Interchangeable onboard telemetry radios

Install one **LR900-A** or **LR24-F-Mini** in the radio area. The user selected
the LR24-F as its **ground unit**; do not add a full-size LR24-F bracket or its
mass to the gondola. Keep the existing central insulating-adhesive pad if the
selected envelope and cable/antenna clearance checks pass. No verified mounting
hole pattern is used for either onboard radio.

## Manufacturer interfaces

| Item | LR900-A | LR24-F-Mini |
| --- | --- | --- |
| Body envelope, long side × width × height | 29.5 × 13 × 9 mm, excludes SMA socket | 24 × 18.2 × 5.8 mm, excludes external antenna/pigtail |
| Published module mass | 4 g | 2.5 g |
| UART connector | GH1.25-4P | SH1.0-4P |
| USB | Type-C, computer/configuration only | None; use a 3.3 V logic USB–UART adapter for setup |
| Antenna connector | SMA, external thread/female centre contact | IPEX1; flexible external T-antenna pictured in package |
| Supply / UART logic | 4.5–5 V / 3.3 V | 4.5–5 V / 3.3 V |
| Maximum average power reference | 0.30 W | 2 W |

Sources: manufacturer [LR900 manual](https://micoair.cn/zh/docs/telemetry/lr900/lr900-telemetry),
[LR24 manual](https://micoair.cn/zh/docs/telemetry/lr24/lr24-telemetry) and
[LR24 store specifications](https://store.micoair.com/wp-content/uploads/2025/01/LR24_params.webp).
The Mini height and IPEX1 identification come from the store specification and
side-view images; the manual's general SMA statement does **not** describe the
bare Mini board. Catalog masses are not installed measurements or full antenna
and harness masses.

## Attachment and wiring limits

A centred adhesive patch within the existing **26 × 10 mm printed pad** has
plan overlap with both boards. LR900-A overhangs it by 1.75 mm at each long end
and 1.5 mm at each side; the Mini overhangs its sides by 4.1 mm, while the pad
projects 1 mm beyond each Mini short end. Trim the actual adhesive to supported
contact and keep the pad's end clear of the plugged SH connector. These are
plan dimensions only. The Mini side photograph shows underside components: use compliant
insulating adhesive and verify a stable supporting surface, component pressure,
heat dissipation and retention on the actual board. No rigid pocket, assumed
flat PCB underside or extra screw pattern is justified by these images.

Revision AR translates the shared pad and its complete radio/connector envelopes
3 mm farther along carrier Y (centre Y=50 mm). The original position left only
0.2 mm between the wider Mini envelope and the FC wiring reservation. The shared
position must pass the same 2 mm minimum FC-neighbour clearance for both radios;
an absence of geometric overlap alone is insufficient.

Place the long axis along the existing radio pad's long axis. Both radios show
UART and RF interfaces at opposite long-axis ends; Mini UART access is from its
short board edge, while the IPEX1 cable mates away from the populated face.
Exact connector XYZ and plugged cable bend radii remain unmeasured. The Mini
photo shows two sockets on one edge, but the manual documents one UART
interface; it does not establish two independent UARTs or the second socket's
function. Route and support the flexible antenna separately from the board,
clear of the propeller swept volumes and optical field; its dimensions are
unpublished in the retained package image.

GH and SH four-pin plugs are not interchangeable. Follow the selected unit's
pin labels, cross TX/RX and connect common GND; connector count alone does not
prove a harness pinout. At 5 V, the average catalog references correspond to
0.06 A and 0.40 A respectively, a calculated **0.34 A increase** for the Mini.
This is not a peak-current prediction or proof of shared FC BEC headroom.

LR900 and LR24 occupy different radio bands and are not a cross-family pair.
Use the matching ground radio and antenna. The selected LR24-F ground unit and
LR24-F-Mini air unit are a supported LR24 pairing; their communication settings
must match. This document establishes interface inputs, not a tested RF link.

## Retained primary evidence

Checked 2026-09-24; original manufacturer images are retained without editing.

| Local file | Original source |
| --- | --- |
| [lr900_variant_dimensions.webp](lr900_variant_dimensions.webp) | [LR900 variant table, including A dimensions and 4 g mass](https://micoair.cn/api/media/file/docs/2026/07/684040d2a4f02-0f3856feb4-010837e548.webp) |
| [lr24_specifications.webp](lr24_specifications.webp) | [LR24 model, dimensions, IPEX1, electrical data](https://store.micoair.com/wp-content/uploads/2025/01/LR24_params.webp) |
| [lr24_dimensions.webp](lr24_dimensions.webp) | [Mini plan and side view, including 5.8 mm height](https://store.micoair.com/wp-content/uploads/2025/01/LR24_size.webp) |
| [lr24f_mini_ports.webp](lr24f_mini_ports.webp) | [Mini SH1.0-4P and pin labels](https://micoair.cn/api/media/file/docs/2026/07/66a0c156834c9-2fc5d7c4ba-76f5fe2816.webp) |
| [lr24f_mini_package.webp](lr24f_mini_package.webp) | [F ground + Mini air package and external T-antenna](https://store.micoair.com/wp-content/uploads/2025/01/LR24FFmini_package.webp) |

Full-size F dimensions and mass differ between the manual drawing and current
store table. This does not affect the requested Mini onboard envelope: the F is
ground equipment and has no fitted CAD interface here. Do not substitute the F
or its drawing for the Mini.
