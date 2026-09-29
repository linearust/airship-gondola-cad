# Selected onboard telemetry radio: LR24-F-Mini

The onboard radio is **LR24-F-Mini only**, paired with **LR24-F on the ground**.
LR900-A is outside current scope. Do not restore it as an alternate
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

The same 64 × 64 × 2 mm square plate is used in all three carrier roles; the
[current plate review](dense_mount_review.md) defines its denser common array.
The Mini uses the navigation carrier's rail-facing face at local (26, −11) mm,
long axis Y, populated face toward −Z and the balloon. It has no separate plate,
pocket or radio-only fastening pattern. Two continuous insulating-adhesive strips,
4 × 15 mm at (23, −7.5) and 3 × 20 mm at (30, −11), lie on opposite sides of the
side-slot row. Each has 60 mm² of complete plate backing and nominal body overlap.
Their total 120 mm² is available contact, not a qualified holding area. The nominal
body overhangs the +X edge by 3.1 mm.

If relocating the radio, recheck the body, both contact strips, connector
reservations, rail-clamp tool approaches and optional-power foot service together.
Source datums in `equipment_mounts.py` and `equipment_layout.py` own the heights.

The adhesive allocation is not a measured bearing face or a qualified area.
The underside photograph shows components: verify insulation, pressure, heat,
actual contact, antenna and lead routing. Wrap Velcro/ties around existing
structure if needed, keeping components and ports clear. Actual balloon curvature
and plugged height remain unmodeled. Remove the carrier for bench installation
and service; this is not proof of on-balloon connector access.

See the [shared plate](dense_mount_review.md) for the array and verification boundary.

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
