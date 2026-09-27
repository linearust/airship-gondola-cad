# Holybro X500 payload-plate reference review

Review date: 2026-09-27. This is reference geometry, not a second definition of
the gondola carrier. The compact 54 × 74 mm carrier is retained. Its project-specific slots are
defined in [mounting_slots.py](../gondola/parts/mounting_slots.py); support lands
and saved-assembly clearances require the current revision checks.

## Identify the plate before claiming compatibility

The current official X500 V2 spare is **Payload Platform Board V2, SKU 31109**,
variant 41591073734845. The V2 assembly guide calls it **#31109 Platform Board**.
The official full-frame STEP contains the corresponding `PLATFORM-PLAT-X500`
part. It measures **93 × 65 × 2 mm** overall. The often-listed 144 × 144 × 2 mm
dimension belongs to an X500 main frame plate, not this payload plate.

The 2019 X500 guide instead calls its part 9 **PAN/TILT platform board**. Its
illustration has a rounded centre, four mounting ears and a different set of
straight radial slots. Its precise dimensions were not established in this
review. Do not apply V2 dimensions to V1. Neither inspected payload-board
illustration establishes curved arc slots.

## V2 geometry extracted from the official STEP

Coordinates below use the plate centre as origin: U follows its 93 mm length,
V its 65 mm width. These are nominal CAD dimensions, not received-part
measurements or manufacturing tolerances.

| Feature | Measured nominal geometry |
| --- | --- |
| Eight central straight slots | Width 3 mm; semicircular ends R1.5 mm |
| Two U-axis slots | End centres at signed U = 8 and 20.5 mm; overall length 15.5 mm |
| Two V-axis slots | End centres at signed V = 8 and 20 mm; overall length 15 mm |
| Four diagonal slots | End centres (±6, ±6) to (±14.838835, ±14.838835), preserving quadrant signs; overall length 15.5 mm |
| Central hole | Ø3 mm |
| Raspberry Pi 4 holes | Ø2.6 mm; 58 × 49 mm pitches in U/V; pattern centres at U = −11 or +11 mm |
| Jetson Nano holes | Ø2.6 mm; centred 86 × 58 mm pitches in U/V |

The guide independently labels the computer pitches as 49 × 58 mm and
58 × 86 mm, and shows M2.5 mounting hardware. It does not provide the central
slot dimensions; those came from the STEP. The radial slots are not all one
identical polar pattern. The central pattern, outer computer holes and
rail-hanger holes serve different interfaces.

The compact [measurement record](holybro_x500_plate_measurements.json) retains
all slot endpoints, computer-hole centres and rail-hanger bores, with source
hashes and the coordinate transformation. The complete 24 MB frame STEP is not
duplicated in this repository.

## Decision for the gondola

Use straight slots as a useful reference, while retaining the smaller project
plate and the confirmed FC/P-AS mounting axes. Copying the complete Holybro
outline and hole pattern would enlarge the plate and remove material from the
gondola's declared central adhesive support regions. The Holybro diagonal
slots do not reproduce the P-AS mounting axes. Dedicated device interfaces and
continuous adhesive lands therefore take priority over reproducing that pattern.

The gondola's revised M2/M3 slot provisions are project-specific. They must be
checked with actual screw heads, nuts, support lands, neighbouring holes and
equipment, including the stack joint. Do not call them an industry-standard
X500 interface or claim drop-in compatibility with the full Holybro payload
plate. A 3 mm nominal metal/carbon-plate slot is also not an established
as-printed M3 clearance for PA12.

## Primary sources

- [Official X500 V2 spares](https://holybro.com/products/spare-parts-x500-v2-kit)
  and [product metadata](https://holybro.com/products/spare-parts-x500-v2-kit.js):
  current name, SKU and variant.
- [Official V2 kit page](https://holybro.com/products/x500-v2-kits) and
  [official documentation](https://docs.holybro.com/drone-development-kit/px4-development-kit-x500v2):
  source of the linked CAD and assembly guide.
- [V2 assembly guide, page 2](https://cdn.shopifycdn.net/s/files/1/0604/5905/7341/files/X500_V2_Assembly_Guide_en.pdf?v=1720853913):
  board identity, computer pitches and mounting hardware.
- [Official full-frame STEP](https://2367252986-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FLIgtGDAvVGkCKGOJb1bR%2Fuploads%2F8i7OGwxNrtr6nOP4BgQ0%2Fx500v2-frame.step?alt=media&token=c06776fd-bd31-40e5-aaa3-9fb56c6ccf5a):
  SHA-256 `e7ccd422cf7825b61ad8270a98d8fbbbc12aced102cc6a20ed17ee66b816c360`.
- [2019 X500 frame-kit guide, pages 1–2](https://cdn.shopify.com/s/files/1/0604/5905/7341/files/Holybro_X500_FrameKit_AssemblyGuide.pdf?v=1646987799),
  linked from [Holybro downloads](https://holybro.com/pages/downloads):
  V1 part identity and visibly different geometry; no inferred slot dimensions.
