"""Measured/provisional equipment envelopes; never exported as printed parts.

All Z values refer to the balloon-facing rail plane Z=0. Device-specific mounts
remain intentionally absent; uncertainty is carried as clearance metadata.
"""

import FreeCAD as App
import Part

from gondola.cad import (
    create_reference,
    set_property,
)
from gondola.design_contract import NOTION_URL

V = App.Vector
FC_SOURCE = "https://micoair.cn/zh/docs/flight-controller/micoair743-aio-series/micoair743v2-aio-35a-manual"
LR_SOURCE = "https://micoair.cn/zh/docs/telemetry/lr900/lr900-telemetry"
PAS_SOURCE = (
    "https://ftp.nooploop.com/downloads/linktrack/LinkTrack_Datasheet_V2.3_zh.pdf"
)
BATTERY_SOURCE = "https://genstattu.com/tattu-450mah-7-4v-75c-2s1p-lipo-battery-pack-with-xt30-plug-long-size-for-h-frame.html"


def build_equipment(doc, battery_group, electronics_group):
    battery = doc.addObject("Part::Box", "ModuleBatteryEnvelope")
    battery_group.addObject(battery)
    battery.Label = "REFERENCE | provisional2S battery, long axisY"
    battery.Length, battery.Width, battery.Height = 61, 16, 15
    for name, value in [("CentreX", 0), ("CentreY", 0), ("BottomZ", 13.2)]:
        set_property(battery, name, value, "App::PropertyDistance")
    set_property(battery, "InPlaneRotation", 90, "App::PropertyAngle")
    battery.setExpression("Placement.Rotation.Angle", "InPlaneRotation")
    battery.Placement.Rotation = App.Rotation(V(0, 0, 1), 90)
    battery.setExpression(
        "Placement.Base.x",
        "CentreX-(Length*cos(InPlaneRotation)-Width*sin(InPlaneRotation))/2",
    )
    battery.setExpression(
        "Placement.Base.y",
        "CentreY-(Length*sin(InPlaneRotation)+Width*cos(InPlaneRotation))/2",
    )
    battery.setExpression("Placement.Base.z", "BottomZ")
    set_property(
        battery,
        "Notes",
        "Same UniversalBoard as FC.1mm nominal adhesive allowance; select actual pack and adhesive. No printed battery attachment patterns.",
    )
    set_property(battery, "SourceURL", BATTERY_SOURCE)
    max_pack = create_reference(
        doc,
        battery_group,
        "MaximumBatteryEnvelope",
        "max reference66x18x17",
        Part.makeBox(18, 66, 17, V(-9, -33, 11)),
        "Maximum prior450mAh reference size only;450–2000mAh is not a physical size guarantee.",
    )
    # Preserve the device's local frame separately from its mounting elevation.
    max_pack.Placement.Base.z = 2.2
    fc = Part.makeBox(36, 36, 8, V(-18, -18, 0))
    for x in (-12.75, 12.75):
        for y in (-12.75, 12.75):
            fc = fc.cut(Part.makeCylinder(1.5, 10, V(x, y, -1)))
    fc.rotate(V(), V(0, 0, 1), -45)
    fc.translate(V(0, 0, 15.2))
    fc_obj = create_reference(
        doc,
        electronics_group,
        "ModuleFCEnvelope",
        "MicoAir743v2-AIO-35A",
        fc,
        "36x36x8mm simplified envelope;3mm stand-off/insulating adhesive allowance above common deck. "
        "No device-specific posts or holes in board; use user-selected insulating adhesive pads on ribs or a removable adapter. "
        "Underside chips, cooling and actual adhesive placement require physical inspection.",
        FC_SOURCE,
    )
    radio = create_reference(
        doc,
        electronics_group,
        "ModuleLR900Envelope",
        "LR900-A on common upper board",
        Part.makeBox(29.5, 13, 9, V(-14.75, 11.5, 41)),
        "Same common upper board atZ44.2 with1mm mounting adhesive allowance; antenna/connectors need actual cable clearance.",
        LR_SOURCE,
    )
    radio.Placement.Base.z = 4.2
    pas_shape = Part.makeBox(32, 27, 7, V(-16, -31, 41))
    pas = create_reference(
        doc,
        electronics_group,
        "ModulePASEnvelope",
        "LinkTrack P-AS on common upper board",
        pas_shape,
        "Planning envelope; adhesive/adapter mounting is separate from the generic board. Antenna and real cable clearance remain to check.",
        PAS_SOURCE,
    )
    pas.Placement.Base.z = 4.2
    refs = [battery, fc_obj, radio, pas]
    clearance = [max_pack]
    auxiliary = [
        (
            "XT30ServiceReserve",
            "XT30 pigtail service reserve10x22x15",
            Part.makeBox(10, 22, 15, V(-30, -11, 45.2)),
        ),
        (
            "CapacitorServiceReserve",
            "35V220uF capacitor reserve diameter10x16",
            Part.makeCylinder(5, 16, V(24, 0, 45.2)),
        ),
    ]
    for name, label, shape in auxiliary:
        o = create_reference(
            doc,
            electronics_group,
            name,
            label,
            shape,
            "Provisional space reservation, not a measured component model or chosen SKU. Latest Notion requires XT30 pigtail and35V220uF capacitor. Mount above upper board with insulating adhesive; keep leads clear.",
            NOTION_URL,
        )
        o.Role = "Clearance"
        o.Label = "RESERVE | " + label
        clearance.append(o)
    return refs, clearance
