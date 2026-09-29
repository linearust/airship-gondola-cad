# Selected parts and preparation

[Final cart evidence, 2026-09-29](cart_selected_parts_2026-09-29.json) preserves
38 relevant rows from all 95 serialized product rows, matching the 95-item
heading. Each retained row includes its original title, exact option, cart
quantity and seller; a clean link is supplementary. Raw account/checkout data,
unrelated products and scripts are omitted. Saved selection is not proof of
payment, delivery, actual dimensions or live availability. The user separately
confirms the generic bearings were purchased.

Use the current generated BOM for installed quantities. Pack contents, spare
stock and mutually exclusive electronic alternatives do not add simultaneous
installed devices.

## Mechanical inputs

| Part | Retained selection / treatment |
| --- | --- |
| Bearings | 3×6×2.5 mm, 10-piece pack; four installed. Keep the purchased generic parts. Manufacturer, shields, race lands, fits and mass are unverified. [Retention](bearing_keeper_review.md) |
| Gears | Kailash m0.5 48T / Ø3 and 16T / Ø3; three of each selected, two of each installed. [Permanent dimension record and drawings](kailash_gears_selected_evidence.md) |
| Shafts | Nominal Ø3 mm 304 stainless: two 200 mm rods and two cart units of 100 mm rod. Tolerance/straightness unverified; precision replacement is allowed if actual fit fails. |
| Servos / horns | Six KST X06 V6.0 selected; two tilt servos modeled. Use the supplied plastic half arm 1 from the [manufacturer archive and exact STEP](servo_horn_compatibility.md), not the superseded metal horns. |
| Motors / propellers | Four RS1102 10000KV motors and four Gemfan 1610 CW/CCW pairs, 1.5 mm bore; two main motors and one propeller pair installed. [Retained motor drawing](rs1102_dimensions.jpg) |
| M1.4 / M1.6 | 500-piece Phillips kit, user-confirmed varied lengths; 100 M1.4 brass nuts and 10 M1.6 nuts. Measure actual head/nut envelopes and engagement. The [M1.6 dimensional reference](ettinger_m1_6_hex_nut.pdf) is not certification of the seller lot. |
| M2 / M3 | Metal screw/nut stock already owned. Current CAD uses ordinary M2 nuts. Ownership does not establish M3 radial gear-screw supply, length, point or projection. |

No purchased bearing spacers. The rejected 3×5×3 bush touches the shield.
Servo Y harnesses, push-on rings, nylon M2 standoffs and unrelated stock are not
requirements. Dedicated tie holes are not required; use existing structure.

## Preparation

| Quantity | Shaft cut length | Flat preparation |
| --- | --- | --- |
| 2 | 34 mm driven output | 5 mm from gear end, nominal 0.5 mm depth; bearing journal stays round |
| 2 | 20 mm opposite output | None |
| 2 | 18 mm input | Full-length flat, nominal 0.5 mm depth; no external bearing journal |

Lengths exclude kerf and finishing. Check received gear/bearing fit before
cutting a batch; cut square and deburr. Do not assign an unpublished h5 fit.
Clock flats to actual screws. Source preparation keys and the matching CAD/BOM
own these dimensions if the mechanism changes.

Horn preparation, screw direction, plain-hole enlargement and ordered service
are specified in [the OEM interface](servo_horn_compatibility.md). Fastener
clearance envelopes are design acceptance limits, not kit measurements.
Keep OEM motor and spline-centre screws where appropriate; their threads and
safe engagement cannot be inferred from the assorted kit.

## Electronics and wiring

The final cart selects the H743V2 AIO **45A AM32/PX4**, Tattu **2S 450 mAh 75C**,
LR24-F + F-Mini pair, XR2 Nano 2.4G and both supported optical/GPS alternatives.
Install only one optical and one navigation module. P-AS is a supported option,
not a required extra purchase when MG-F10 or M10 Ultra is used. The selected FC's
**2S support is user-confirmed**; actual revision, damper stack, insulation,
underbody wire clearance and installed power still require checks.

One BEC12S-PRO and the five-piece SVPDB-8S option are present. A supported tether
installation uses one of each, not every purchased board. Read the
[power topology and limits](power_module_compatibility.md).

GH1.25 stock is owned; SH1.0 kits, extension leads, raw wire and power leads are
retained in the cart record. They do not establish complete pinouts, finished
harness lengths, antenna extensions, tether rating, a PSU, or actual adhesive
retention. No missing purchase is inferred merely because generic supplies are
not visible. Inspect installed fit and routing before flight.
