"""Measured/provisional equipment envelopes; never exported as printed parts.

All Z values refer to the balloon-facing rail plane Z=0. Confirmed hole axes are
represented; unpublished PCB bearing planes and fastener stacks remain unknown.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import (
    create_reference,
    set_property,
)
from gondola.design_contract import NOTION_URL

from . import equipment_mounts as mounts
from . import mounting_interfaces as interfaces

V = App.Vector
FC_SOURCE = interfaces.FC_SOURCE
LR_SOURCE = interfaces.LR_SOURCE
PAS_SOURCE = interfaces.PAS_SOURCE
BATTERY_SOURCE = "https://genstattu.com/tattu-450mah-7-4v-75c-2s1p-lipo-battery-pack-with-xt30-plug-long-size-for-h-frame.html"
MTF02P_SOURCE = interfaces.MTF02P_SOURCE
MTF02P_PRODUCT_SOURCE = interfaces.MTF02P_PRODUCT_SOURCE
MTF02P_DIMENSION_IMAGE = interfaces.MTF02P_DIMENSION_IMAGE
MTF02P_SIZE_MM = interfaces.MTF02P_SIZE_MM
MTF02P_CENTRE_XY = mounts.MTF02P_CENTRE_XY
MTF02P_BOTTOM_Z = mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE
MTF02P_MASS_G = interfaces.MTF02P_MASS_G
MTF02P_FLOW_FOV_DEG = interfaces.MTF02P_FLOW_FOV_DEG
MTF02P_TOF_FOV_DEG = interfaces.MTF02P_TOF_FOV_DEG
MTF02P_OPTICAL_RESERVE_MM = 80.0
FC_BOTTOM_Z = mounts.SUPPORT_FACE_Z + mounts.FC_WIRING_CLEARANCE
PAS_BOTTOM_Z = mounts.SUPPORT_FACE_Z + mounts.PAS_SERVICE_CLEARANCE
LR_BOTTOM_Z = mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE


def fc_envelope_shape():
    """Published overall envelope and hole XY axes; the PCB plane is unknown."""
    length, width, height = interfaces.FC_SIZE_MM
    shape = Part.makeBox(length, width, height, V(-length / 2, -width / 2, 0))
    for x, y in interfaces.FC_HOLE_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(interfaces.FC_HOLE_DIAMETER / 2, height + 2, V(x, y, -1))
        )
    shape.rotate(V(), V(0, 0, 1), mounts.FC_ROTATION_DEG)
    shape.translate(V(*mounts.FC_CENTRE_XY, FC_BOTTOM_Z))
    return shape


def pas_envelope_shape():
    """Use the source drawing frame: X width 27, Y length 32, antenna +Y."""
    length, width, height = interfaces.PAS_SIZE_MM
    x, y = mounts.PAS_CENTRE_XY
    shape = Part.makeBox(
        length, width, height, V(x - length / 2, y - width / 2, PAS_BOTTOM_Z)
    )
    for hx, hy in mounts.PAS_HOLE_CENTRES:
        shape = shape.cut(
            Part.makeCylinder(
                interfaces.PAS_HOLE_DIAMETER / 2,
                height + 2,
                V(hx, hy, PAS_BOTTOM_Z - 1),
            )
        )
    return shape


def lr900_envelope_shape():
    """The published LR900-A size excludes its SMA socket and antenna."""
    length, width, height = interfaces.LR_SIZE_MM
    x, y = mounts.LR_CENTRE_XY
    return Part.makeBox(
        length, width, height, V(x - length / 2, y - width / 2, LR_BOTTOM_Z)
    )


def _interface_metadata(obj, key, hole_centres=(), hole_diameter=None):
    set_property(
        obj,
        "MountingEvidence",
        json.dumps(interfaces.MOUNTING_EVIDENCE[key], sort_keys=True),
    )
    set_property(obj, "MountingStackVerified", False, "App::PropertyBool")
    set_property(obj, "PCBHeightMeasured", False, "App::PropertyBool")
    if hole_diameter is not None:
        set_property(
            obj, "PublishedMountHoleDiameter", hole_diameter, "App::PropertyLength"
        )
        set_property(
            obj,
            "VerifiedHoleAxesXY",
            [V(x, y, 0) for x, y in hole_centres],
            "App::PropertyVectorList",
        )
        set_property(
            obj,
            "HoleAxisScope",
            "XY axes only. Cylindrical cuts pass through the reference envelope for registration; no real PCB thickness or bearing-plane Z is claimed.",
        )


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
    for name, value in [
        ("CentreX", 0),
        ("CentreY", 0),
        ("BottomZ", mounts.SUPPORT_FACE_Z + mounts.ADHESIVE_ALLOWANCE),
    ]:
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
        "Dedicated continuous 16x52mm adhesive deck; 1mm nominal insulating adhesive allowance. Select and verify actual pack, adhesive area and retention. No battery hole pattern is invented.",
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
    fc_obj = create_reference(
        doc,
        electronics_group,
        "ModuleFCEnvelope",
        "MicoAir743v2-AIO-35A",
        fc_envelope_shape(),
        "Published36x36x8mm envelope; confirmed25.5mm square hole pattern and diameter3mm, rotated-45deg. "
        "Our carrier provides M2 clearance holes on these XY axes. The included four M2x7.5mm silicone dampening sleeves are purchased parts; their compressed geometry is not modeled. "
        "An8mm design allowance separates the component-envelope minimum from the carrier face, with an open-X wiring corridor. This is not a manufacturer-required spacer height or PCB bearing-plane location. "
        "Actual spacer/bolt lengths, underside components, connectors, ventilation and strain relief remain to verify.",
        FC_SOURCE,
    )
    _interface_metadata(
        fc_obj, "FC", mounts.FC_HOLE_CENTRES, interfaces.FC_HOLE_DIAMETER
    )
    set_property(
        fc_obj,
        "PublishedMountHolePitch",
        interfaces.FC_HOLE_PITCH,
        "App::PropertyLength",
    )
    set_property(fc_obj, "DimensionDrawingSource", interfaces.FC_DIMENSION_SOURCE)
    set_property(fc_obj, "IncludedDamperSource", interfaces.FC_PACKAGE_SOURCE)
    set_property(
        fc_obj,
        "DesignUnderbodyClearance",
        mounts.FC_WIRING_CLEARANCE,
        "App::PropertyLength",
    )
    radio = create_reference(
        doc,
        electronics_group,
        "ModuleLR900Envelope",
        "LR900-A on continuous adhesive pad",
        lr900_envelope_shape(),
        "Published29.5x13x9mm body excludes SMA antenna socket. Provisional1mm insulating adhesive allowance above the continuous carrier pad. No verified mounting-hole pattern. Actual underside contact, antenna, connector insertion and cable bend clearance remain unmeasured.",
        LR_SOURCE,
    )
    _interface_metadata(radio, "LR")
    pas = create_reference(
        doc,
        electronics_group,
        "ModulePASEnvelope",
        "LinkTrack P-AS | confirmed two M2 mounting axes",
        pas_envelope_shape(),
        "Official drawing frame X27xY32mm, antenna+Y; two diameter2.2mm holes spaced23mm,6.7mm from the connector-side edge. "
        "The specification table lists7mm overall height while the mechanical drawing shows5.3mm; retain7mm conservatively. "
        "Our4mm underbody service allowance is not a measured PCB bearing-plane height. Buy the spacer/fastener stack after checking actual PCB, antenna and GH1.25 connector access; no unverified mounting hardware is generated.",
        PAS_SOURCE,
    )
    _interface_metadata(
        pas, "PAS", mounts.PAS_HOLE_CENTRES, interfaces.PAS_HOLE_DIAMETER
    )
    set_property(
        pas, "PublishedMountHolePitch", interfaces.PAS_HOLE_PITCH, "App::PropertyLength"
    )
    set_property(
        pas,
        "DesignUnderbodyClearance",
        mounts.PAS_SERVICE_CLEARANCE,
        "App::PropertyLength",
    )
    mtf = create_reference(
        doc,
        electronics_group,
        "ModuleMTF02PEnvelope",
        "MicoAir MTF-02P | optical face away from balloon (+Z)",
        mtf02p_envelope_shape(),
        "Published21.6x16x6.5mm overall envelope and1.5g module mass. Provisional insulating adhesive on the continuous carrier pad leaves1mm mounting allowance. "
        "The optical/component face points toward world+Z, away from balloon planeZ0. Match the purchased board orientation and firmware rotation setting; no default in-plane yaw is claimed. "
        "Backside components, adhesive contact/retention and cable routing require the actual sensor. No mounting-hole pattern or retaining screw is assumed.",
        MTF02P_SOURCE,
    )
    _interface_metadata(mtf, "MTF02P")
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
    wiring = create_reference(
        doc,
        electronics_group,
        "FCWiringClearanceReserve",
        "FC underbody open-X wiring corridor | design allowance8mm",
        mounts.fc_wiring_reserve_shape(),
        "Our8mm free-height,8mm-wide X corridor atY5..13 below the full FC component envelope. Both X ends remain open and the route avoids the confirmed mounting axes. This is a routing reservation, not an exact cable model, measured connector clearance or selected spacer/bolt length. Actual damper outside dimensions remain unknown. Keep wires clear of ESC cooling and remove the module before clamp service.",
        FC_SOURCE,
    )
    wiring.Role = "Clearance"
    wiring.Label = "RESERVE | FC underbody wiring corridor"
    set_property(
        wiring,
        "DesignClearanceHeight",
        mounts.FC_WIRING_CLEARANCE,
        "App::PropertyLength",
    )
    set_property(wiring, "ManufacturerSpecifiedHeight", False, "App::PropertyBool")
    clearance = [max_pack, optical, wiring]
    auxiliary = [
        (
            "XT30ServiceReserve",
            "XT30 pigtail service reserve10x22x15",
            Part.makeBox(10, 22, 15, V(-43, -11, 13.2)),
        ),
        (
            "CapacitorServiceReserve",
            "35V220uF capacitor reserve diameter10x16",
            Part.makeCylinder(5, 16, V(30, 22, 13.2)),
        ),
    ]
    for name, label, shape in auxiliary:
        o = create_reference(
            doc,
            electronics_group,
            name,
            label,
            shape,
            "Provisional space reservation, not a measured component model, selected SKU or designed retaining mount. Latest Notion requires XT30 pigtail and35V220uF capacitor. Final insulation, lead routing and mechanical retention remain to be selected; no printed attachment or invented hole is added.",
            NOTION_URL,
        )
        o.Role = "Clearance"
        o.Label = "RESERVE | " + label
        clearance.append(o)
    return refs, clearance
