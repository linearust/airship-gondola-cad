# Selected controller: MicoAir743v2-AIO-45A

Reviewed 2026-09-24. The user replaced the 35A Bluejay board with the H743V2
AIO 45A AM32 board. This is a component selection and CAD interface review,
not confirmation that the selected battery powers every supplied board revision.

## Mechanical interface

The [45A manufacturer manual](https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-45a-manual)
and [45A product page](https://micoair.com/flightcontroller_micoair743v2_aio_45a/)
agree on a 36 × 36 × 8 mm envelope, 25.5 × 25.5 mm mounting pattern,
Ø3 mm mounting holes and 10 g nominal mass. These match the previous board's
nominal CAD interface. The manual specifies 45° installation, insulation and
damping, with the board arrow forward and ESC regions ventilated.

The [45A package image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Package.webp)
labels four M2 × 6.6 mm silicone dampers; the previous 35A package labels
M2 × 7.5 mm. Neither specifies a PCB bearing plane, groove dimensions or
compressed height. Do not use either nominal damper length as the underside
clearance, or infer a final mounting screw length from it. Preserve the designed
wire space and verify the received mounting stack before assembly.

No separate dimensioned 45A mechanical drawing was found. The specifications
table supplies nominal dimensions, not a tolerance drawing or connector datum.

## Ports and clearance

The [45A front/back interface image](https://micoair.cn/api/media/file/docs/2026/07/67d99cd088539-3afa75c002-90182857a6.webp)
shows the same broad connector locations as the previous board: UART3/I²C and
DJI on the upper face; UART1/UART6 and UART4 underneath; USB Type-C at an edge.
The package identifies SH1.0-6P and SH1.0-4P harnesses, and the manual identifies
the DJI SH1.0-6P port. The illustrated pin counts are three six-pin headers and
one four-pin header. The DJI port includes 12 V; it is not a general 5 V port.

This visual comparison supports retaining the generic peripheral service band
and underside wiring reserve. It does **not** verify individual connector XYZ,
plug protrusion, cable bend radius or access with the actual harness. Do not
transfer exact port coordinates from a 35A photograph or invent new close-fitting
openings. Changes in ESC components also do not establish identical local
component heights from photographs.

## Conflicting input-voltage evidence

The current 45A manual, product page and [store title](https://store.micoair.com/product/micoair743v2-aio-45a/)
state **3–6S**, with manual/product text giving **10–27 V**. However, the
manufacturer's linked 45A port illustration states **2–6S, 5.6–27 V**, and its
[45A specifications image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Specifications.webp)
states **2S–6S** alongside AM32 and 45A × 4. This is a conflict within official
sources, not sufficient evidence to declare the user's product title mistaken.
The older image also lists ESC firmware 2.17 while current text lists 2.19;
neither proves a hardware revision boundary or the received firmware.

Keep the user-selected 45A board and existing 2S battery in the CAD selection.
Record 2S electrical compatibility as unresolved until the actual revision's
manufacturer specification is confirmed. Do not silently change the battery,
motors, or wiring power rails. Nominal mechanical fit does not resolve this issue.

## Retained primary images

| Local file | Official source |
| --- | --- |
| [45A specifications](micoair743v2_aio45a_specifications.webp) | [Store image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Specifications.webp) |
| [45A package](micoair743v2_aio45a_package.webp) | [Store image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Package.webp) |
| [45A ports](micoair743v2_aio45a_ports.webp) | [Manual image](https://micoair.cn/api/media/file/docs/2026/07/67d99cd088539-3afa75c002-90182857a6.webp) |
| [45A installation illustration](micoair743v2_aio45a_orientation.webp) | [Manual image](https://micoair.cn/api/media/file/docs/2026/07/7a5ab686921e08331f0d5a4fdbd5ee3a-a8f6b818fd-9e9255a2f4.webp) |

The live English product page's gallery/port image links returned 404 during
this review; the manual and official store image URLs above were accessible.
The 45A manual's firmware introduction still names the 35A board, another
editing inconsistency; it is not a basis for retaining the old controller model.
