"""Measured/provisional equipment envelopes; never exported as printed parts.

All Z values refer to the balloon-facing rail plane Z=0. Device-specific mounts
remain intentionally absent; uncertainty is carried as clearance metadata.
"""

import math

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
MTF02P_SOURCE = "https://micoair.cn/zh/docs/sensors/sensors/mtf-02-02p-sensors"
MTF02P_PRODUCT_SOURCE = "https://micoair.com/optical_range_sensor_mtf-02p/"
MTF02P_DIMENSION_IMAGE = "https://micoair.cn/api/media/file/docs/2026/07/66f661b664e82-df0e9d69d2-971f59dd57.webp"
MTF02P_SIZE_MM = (21.6, 16.0, 6.5)
MTF02P_CENTRE_XY = (0.0, 5.0)
MTF02P_BOTTOM_Z = 45.2
MTF02P_MASS_G = 1.5
MTF02P_FLOW_FOV_DEG = 42.0
MTF02P_TOF_FOV_DEG = 2.0
MTF02P_OPTICAL_RESERVE_MM = 80.0


def mtf02p_envelope_shape():
    """Published overall size, with the component/optical face toward +Z."""
    length, width, height = MTF02P_SIZE_MM
    x, y = MTF02P_CENTRE_XY
    return Part.makeBox(
        length,
        width,
        height,
        V(x - length / 2, y - width / 2, MTF02P_BOTTOM_Z),
    )


def mtf02p_optical_reserve_shape():
    """Expand the entire front face; no unpublished lens origin is assumed."""
    length, width, height = MTF02P_SIZE_MM
    x, y = MTF02P_CENTRE_XY
    sections = []
    for distance in (0.0, MTF02P_OPTICAL_RESERVE_MM):
        expansion = distance * math.tan(math.radians(MTF02P_FLOW_FOV_DEG / 2))
        half_x, half_y = length / 2 + expansion, width / 2 + expansion
        z = MTF02P_BOTTOM_Z + height + distance
        points = [
            V(x - half_x, y - half_y, z),
            V(x + half_x, y - half_y, z),
            V(x + half_x, y + half_y, z),
            V(x - half_x, y + half_y, z),
        ]
        sections.append(Part.makePolygon(points + [points[0]]))
    return Part.makeLoft(sections, True, True)


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
        Part.makeBox(29.5, 13, 9, V(-14.75, 15.5, 41)),
        "Same common upper board atZ44.2 with1mm mounting adhesive allowance. Shifted4mm toward+Y to leave at least1mm nominal clearance from the conservative MTF-02P optical reserve; antenna/connectors need actual cable clearance.",
        LR_SOURCE,
    )
    radio.Placement.Base.z = 4.2
    pas_shape = Part.makeBox(32, 27, 7, V(-16, -32, 41))
    pas = create_reference(
        doc,
        electronics_group,
        "ModulePASEnvelope",
        "LinkTrack P-AS on common upper board",
        pas_shape,
        "Planning envelope shifted1mm toward-Y to leave at least1mm nominal clearance from the conservative MTF-02P optical reserve. Adhesive/adapter mounting is separate from the generic board. Antenna and real cable clearance remain to check.",
        PAS_SOURCE,
    )
    pas.Placement.Base.z = 4.2
    mtf = create_reference(
        doc,
        electronics_group,
        "ModuleMTF02PEnvelope",
        "MicoAir MTF-02P | optical face away from balloon (+Z)",
        mtf02p_envelope_shape(),
        "Published21.6x16x6.5mm overall envelope and1.5g module mass. Provisional insulating adhesive pads on the upper board leave1mm mounting allowance. "
        "The optical/component face points toward world+Z, away from balloon planeZ0. Match the purchased board orientation and firmware rotation setting; no default in-plane yaw is claimed. "
        "Backside components, adhesive contact/retention and cable routing require the actual sensor. No mounting-hole pattern or retaining screw is assumed.",
        MTF02P_SOURCE,
    )
    set_property(mtf, "ProductSource", MTF02P_PRODUCT_SOURCE)
    set_property(mtf, "DimensionDrawingSource", MTF02P_DIMENSION_IMAGE)
    set_property(mtf, "ListedMassGrams", MTF02P_MASS_G, "App::PropertyFloat")
    set_property(mtf, "OpticalDirection", V(0, 0, 1), "App::PropertyVector")
    set_property(
        mtf, "PublishedOpticalFlowFOV", MTF02P_FLOW_FOV_DEG, "App::PropertyAngle"
    )
    set_property(mtf, "PublishedToFFOV", MTF02P_TOF_FOV_DEG, "App::PropertyAngle")
    set_property(mtf, "OpticalOriginsMeasured", False, "App::PropertyBool")
    optical = create_reference(
        doc,
        electronics_group,
        "MTF02POpticalClearanceReserve",
        "MTF-02P whole-face optical clearance | +Z, first80mm",
        mtf02p_optical_reserve_shape(),
        "Conservative geometric reservation: the entire21.6x16mm front face expands21deg per side in both axes for80mm toward+Z. "
        "The manufacturer publishes42deg optical-flow FOV and2deg ToF FOV, but exact lens origins, angular-axis definitions and installed usable field are unmeasured. "
        "This near-field obstruction screen is not a calibrated camera model, full-range ground visibility proof or validated cable route. Keep adhesives and wires outside the optical face and reserve; verify the purchased sensor and firmware orientation.",
        MTF02P_SOURCE,
    )
    optical.Role = "Clearance"
    optical.Label = "RESERVE | MTF-02P optical field away from balloon"
    set_property(
        optical,
        "ReservedOpticalDistance",
        MTF02P_OPTICAL_RESERVE_MM,
        "App::PropertyLength",
    )
    set_property(optical, "OpticalDirection", V(0, 0, 1), "App::PropertyVector")
    set_property(optical, "InstalledOpticalFieldVerified", False, "App::PropertyBool")
    refs = [battery, fc_obj, radio, pas, mtf]
    clearance = [max_pack, optical]
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
