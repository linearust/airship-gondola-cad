# Selected controller: MicoAir743v2-AIO-45A

Updated 2026-09-29: **the user confirmed that the selected H743V2 AIO 45A AM32
board supports 2S**. Retain the existing 2S battery; its compatibility is no longer
an unresolved selection issue. The user suspects a recent model change, but no
hardware revision number or change history was provided. This confirmation does
not establish an exact minimum input voltage or qualify the installed power system.

## Mechanical interface

The [45A manufacturer manual](https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-45a-manual)
and [45A product page](https://micoair.com/flightcontroller_micoair743v2_aio_45a/)
were reviewed for a 36 × 36 × 8 mm envelope, 25.5 × 25.5 mm mounting pattern,
Ø3 mm mounting holes and 10 g nominal mass. The manual specifies 45° installation, insulation and
damping, with the board arrow forward and ESC regions ventilated.

The [45A package image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Package.webp)
labels four M2 × 6.6 mm silicone dampers. It does not specify a PCB bearing plane,
groove dimensions or compressed height. Do not use nominal damper length as the underside
clearance, or infer a final mounting screw length from it. Preserve the designed
wire space and verify the received mounting stack before assembly.

No separate dimensioned 45A mechanical drawing was found. The specifications
table supplies nominal dimensions, not a tolerance drawing or connector datum.

## Ports and clearance

The [45A front/back interface image](https://micoair.cn/api/media/file/docs/2026/07/67d99cd088539-3afa75c002-90182857a6.webp)
shows UART3/I²C and
DJI on the upper face; UART1/UART6 and UART4 underneath; USB Type-C at an edge.
The package identifies SH1.0-6P and SH1.0-4P harnesses, and the manual identifies
the DJI SH1.0-6P port. The illustrated pin counts are three six-pin headers and
one four-pin header. The DJI port includes 12 V; it is not a general 5 V port.

These images support a generic peripheral service band and underside wiring reserve. It does **not** verify individual connector XYZ,
plug protrusion, cable bend radius or access with the actual harness. Do not
derive exact port coordinates or close-fitting openings from photographs.

## Voltage and revision boundary

Earlier manufacturer text and illustrations conflicted on the minimum input.
Use the user's 2S confirmation for the selected board; the exact hardware revision,
minimum operating voltage and installed regulator behavior remain unverified.
Do not infer a cutoff voltage from an illustration. An 8 V main rail is nominally
consistent with standard 2S operation, but startup, transients, current demand,
cooling and shared 5 V capacity need installed-system checks.

## Retained primary images

| Local file | Official source |
| --- | --- |
| [45A specifications](micoair743v2_aio45a_specifications.webp) | [Store image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Specifications.webp) |
| [45A package](micoair743v2_aio45a_package.webp) | [Store image](https://store.micoair.com/wp-content/uploads/2025/03/H743V2-AIO_Package.webp) |
| [45A ports](micoair743v2_aio45a_ports.webp) | [Manual image](https://micoair.cn/api/media/file/docs/2026/07/67d99cd088539-3afa75c002-90182857a6.webp) |
| [45A installation illustration](micoair743v2_aio45a_orientation.webp) | [Manual image](https://micoair.cn/api/media/file/docs/2026/07/7a5ab686921e08331f0d5a4fdbd5ee3a-a8f6b818fd-9e9255a2f4.webp) |
