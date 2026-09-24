# Interchangeable optical sensors

Use exactly one MicoAir MTF-02P or MTF-01P on the existing manual roll/pitch
optical stack. MTF-02P remains the default. The sensor choice does not add a
second sensor, printed part or mounting fastener. The complete stack remains
transferable between the battery and electronics carriers.

## Published interfaces

| Item | MTF-02P | MTF-01P |
| --- | --- | --- |
| Nominal envelope, long side × width × height | 21.6 × 16 × 6.5 mm | 33.2 × 20.8 × 16.8 mm |
| Published mass | 1.5 g | 8 g |
| Mounting holes | No confirmed hole pattern | Four Ø2.5 mm holes, 24.3 × 12 mm pitch; unused by this mount |
| Optical-flow / range FOV | 42° / 2° | 42° / 1.5° |
| Connector | SH1.0-4P on a short edge | SH1.0-4P on a long edge |
| Chosen connector exit in tray coordinates | +X | +Y |

Dimensions and specifications come from the manufacturer's
[MTF-02/02P manual](https://micoair.cn/zh/docs/sensors/sensors/mtf-02-02p-sensors)
and [MTF-01P manual](https://micoair.cn/zh/docs/sensors/sensors/mtf-01p-sensors).
The signed CAD directions are installation choices; the photographs establish
which edge carries the connector, not a manufacturer-defined CAD frame.

## Shared attachment

Retain the continuous **18 × 12 mm adhesive tray** and its 1 mm nominal
insulating-adhesive allowance. Center either sensor's rear face on the tray.
The MTF-01P rear photograph shows a broad enclosed case, making central tape
attachment credible without a new bracket or reproducing its mounting holes.
Its nominal centered overhang is 7.6 mm along each long-side end and 4.4 mm
along each width-side end. These dimensions do not certify adhesive strength,
rear-face flatness or the manual clamps' holding torque under the heavier
sensor. Check actual seating, retention and pointing before use.

Keep adhesive away from connectors and optical apertures. A cable tie must not
cross the optical face, its three apertures or raised range-sensor tubes. No
qualified tie path or extra tie slot is assumed; rear-face tape is the basic
attachment method. Actual harness slack must follow both manual axes without
pulling the sensor.

## Optical and connector screening assumptions

Use each selected model's envelope and connector edge. The 12 mm outward
connector corridor is a design allowance, not a measured extraction stroke or
bend radius. Exact port height and lateral datum remain unmeasured.

For **both** models, conservatively expand the whole plan footprint from the
rear/body-bottom plane along local +Z, using the published 42° full angle in
both transverse axes. This intentionally includes the body depth and begins
behind any possible front aperture. The MTF-01P's 16.8 mm overall height
includes raised range-sensor tubes; it is not the optical-flow lens datum.
This common screen avoids assuming that the two lens origins share the
furthest front plane. Exclude the selected sensor itself from this clearance
screen, while checking surrounding parts for both hosts and the manual angle
range. The conservative field may also overlap the sensor's own edge-access
lane because individual lens and connector datums are unknown. That reservation
overlap is intentional; it does not certify a real connected cable's optical
clearance. External reservations remain obstacles. The angular-axis convention, lens origins and installed optical field
remain unmeasured; this is not optical calibration or flight qualification.

Follow the selected model's firmware-orientation drawing. Both manuals show
opposite forward arrows for ArduPilot/PX4 versus INAV (MTF-01P also lists FMT).
The drawings use different device presentations; do not copy the previous
sensor's yaw setting merely because the connector fits.

## Retained primary evidence

Checked 2026-09-24. Local files retain the original manufacturer images.

| Local file | Original source |
| --- | --- |
| [mtf01p_dimensions.webp](mtf01p_dimensions.webp) | [MTF-01P envelope, holes and mass](https://micoair.cn/api/media/file/docs/2026/07/66b4374b5dc9c-85c984aa0c-4b3c55e69c.webp) |
| [mtf01p_ports.webp](mtf01p_ports.webp) | [MTF-01P rear case, SH1.0-4P and pin labels](https://micoair.cn/api/media/file/docs/2026/07/66b437e3092ef-ce4191a0f2-dfd02307eb.webp) |
| [mtf01p_orientation.webp](mtf01p_orientation.webp) | [MTF-01P firmware-dependent forward arrows](https://micoair.cn/api/media/file/docs/2026/07/66b43805576df-07a5fca3b2-9ceca549ba.webp) |
| [mtf02p_dimensions.webp](mtf02p_dimensions.webp) | [MTF-02P envelope](https://micoair.cn/api/media/file/docs/2026/07/66f661b664e82-df0e9d69d2-971f59dd57.webp) |
| [mtf02p_ports.webp](mtf02p_ports.webp) | [MTF-02P connector](https://micoair.cn/api/media/file/docs/2026/07/66f66374dd95c-852bf87918-83cf12d631.webp) |
| [mtf02p_firmware_orientation.webp](mtf02p_firmware_orientation.webp) | [MTF-02/02P firmware-dependent forward arrows](https://micoair.cn/api/media/file/docs/2026/07/66f6639242746-8204f1d31b-afb417fc40.webp) |

These references establish the design inputs and limits. Validation results
belong to the generated reports for the saved CAD and selected sensor profile.
