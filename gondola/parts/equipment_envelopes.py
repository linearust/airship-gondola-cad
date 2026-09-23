"""Measured/provisional equipment envelopes; never exported as printed parts.

All Z values refer to the balloon-facing rail plane Z=0. Confirmed hole axes are
represented; unpublished PCB bearing planes and fastener stacks remain unknown.
"""

import json

import FreeCAD as App
import Part

from gondola.cad import (
    create_reference,
    set_property,
)
from gondola.contracts import equipment_interfaces as interfaces
from gondola.contracts.design import NOTION_URL

from . import equipment_mounts as mounts
from . import wiring_reserves
from .equipment_metadata import add_interface_metadata, create_wiring_reserve

V = App.Vector
FC_SOURCE = interfaces.FC_SOURCE
LR_SOURCE = interfaces.LR_SOURCE
PAS_SOURCE = interfaces.PAS_SOURCE
BATTERY_SOURCE = "https://genstattu.com/tattu-450mah-7-4v-75c-2s1p-lipo-battery-pack-with-xt30-plug-long-size-for-h-frame.html"
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
        "Dedicated continuous 16x52mm adhesive deck; 1mm nominal insulating adhesive allowance. Geometric centre adjustment is limited to +/-5mm X and +/-4mm Y to keep the stock optical-stack columns clear. Move the rail carrier for larger trim changes. Select and verify actual pack, adhesive area and retention. No battery hole pattern is invented.",
    )
    set_property(battery, "SourceURL", BATTERY_SOURCE)
    set_property(
        battery,
        "BatteryPlacementContract",
        json.dumps(mounts.BATTERY_PLACEMENT_CONTRACT, sort_keys=True),
    )
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
    add_interface_metadata(
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
    add_interface_metadata(radio, "LR")
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
    add_interface_metadata(
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
    refs = [battery, fc_obj, radio, pas]
    clearance = [max_pack]
    contracts = wiring_reserves.reserve_contracts()
    for name, shape in wiring_reserves.reserve_shapes().items():
        contract = contracts[name]
        reserve = create_wiring_reserve(doc, electronics_group, name, shape, contract)
        if name == "FCWiringClearanceReserve":
            set_property(
                reserve,
                "DesignClearanceHeight",
                mounts.FC_WIRING_CLEARANCE,
                "App::PropertyLength",
            )
            set_property(
                reserve, "ManufacturerSpecifiedHeight", False, "App::PropertyBool"
            )
        clearance.append(reserve)
    capacitor = create_reference(
        doc,
        electronics_group,
        "CapacitorServiceReserve",
        "35V220uF capacitor reserve diameter10x16",
        Part.makeCylinder(5, 16, V(36, 22, 13.2)),
        "Provisional space for the specified35V220uF capacitor, not a selected component or retaining mount. Insulation, leads, actual dimensions and retention remain to be selected; no printed attachment or invented hole is added.",
        NOTION_URL,
    )
    capacitor.Role = "Clearance"
    capacitor.Label = "RESERVE | 35V220uF capacitor"
    clearance.append(capacitor)
    return refs, clearance
