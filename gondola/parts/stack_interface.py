"""Removable one-piece optical portal on two bought carbon25.5mm axes.

The lower carbon plate clamps to the rail through separate16mm axes. The
portal feet use the two25.5mm X axes, independently of FC soft retention.
"""

import json
import math

import FreeCAD as App
import Part

from gondola.cad import belongs_to_group, box, set_property, union
from gondola.contracts import stack_adapter as adapter_specification
from gondola.contracts.design import STACK_ANCHOR_CENTRES, STACK_PITCH_MM

V = App.Vector
PITCH_MM = STACK_PITCH_MM
ANCHOR_CENTRES = STACK_ANCHOR_CENTRES
FOOT_CENTRES = tuple(
    (x, y) for x, y in adapter_specification.COMMON_HOLE_CENTRES if abs(x) > 1
)
FOOT_DIAMETER = 6.0
FOOT_HOLE_DIAMETER = 2.6
HOST_SUPPORT_Z = 8.0
STACK_TOP_Z = 51.3
TOWER_HEIGHT = STACK_TOP_Z - HOST_SUPPORT_Z
TOP_BEAM_THICKNESS = 3.0
FIXED_LEG_INNER = -1.4
FIXED_LEG_THICKNESS = 2.0
LEG_WIDTH = 8.0
ROOT_ARM_BOTTOM_Z = HOST_SUPPORT_Z
ROOT_ARM_THICKNESS = 2.0
ROOT_ARM_WIDTH = 6.0
LEG_BOTTOM_Z = ROOT_ARM_BOTTOM_Z - STACK_TOP_Z
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "StockBatteryAdapter",
    "ElectronicsEquipmentModule": "StockFCAdapter",
}
MECHANICAL_HOSTS = {
    **SUPPORTED_HOSTS,
    "AccessoryEquipmentModule": "StockNavigationAdapter",
}
HOST_ORIGINS_XY = {name: (0.0, 0.0) for name in MECHANICAL_HOSTS}
HOST_ORIGINS_XY["AccessoryEquipmentModule"] = (24.0, 0.0)
FOOT_HARDWARE_NAMES = tuple(
    "OpticalFoot" + str(i) + kind for i in range(2) for kind in ("Bolt", "Nut")
)


def host_origin_xy(host_name=None):
    if host_name is None:
        return (0.0, 0.0)
    for group, part in MECHANICAL_HOSTS.items():
        if host_name in (group, part):
            return HOST_ORIGINS_XY[group]
    raise ValueError("Unknown carbon stack host: " + str(host_name))


def host_placement(host_name, z=HOST_SUPPORT_Z):
    return App.Placement(V(*host_origin_xy(host_name), z), App.Rotation())


def interface_contract(host_name=None):
    return {
        "construction": "One-piece removable PA12 portal on purchased carbon",
        "industry_standard_claimed": False,
        "anchor_centres_xy_mm": ANCHOR_CENTRES,
        "foot_centres_xy_mm": FOOT_CENTRES,
        "foot_hole_diameter_mm": FOOT_HOLE_DIAMETER,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "integral_tower_height_mm": TOWER_HEIGHT,
        "stack_platform_bottom_z_mm": STACK_TOP_Z,
        "lower_root_arm_bottom_z_mm": ROOT_ARM_BOTTOM_Z,
        "lower_root_arm_section_mm": [ROOT_ARM_THICKNESS, ROOT_ARM_WIDTH],
        "fixed_load_leg_section_mm": [FIXED_LEG_THICKNESS, LEG_WIDTH],
        "top_beam_section_mm": [TOP_BEAM_THICKNESS, LEG_WIDTH],
        "separate_base_print_count": 1,
        "detachable_foot_joint": True,
        "tower_attachment": "Two opposed25.5mm X axes secure the portal to the bought carbon. On the battery plate use twoM2x6 screws upward through carbon and2mm feet, with ordinaryM2 nuts above. At the FC reuse its two X-axisM2x20 studs, seating the corresponding intermediate nuts above the feet. The other two FC studs remain unchanged. No printed lower mounting plate or rail shoe.",
        "load_path": "Optical pivot -> integral beam/legs/feet -> two25.5mm carbon axes -> laminate -> independent two16mm rail clamps -> twin tracks. The light optical support deliberately uses carbon structurally; laminate contact, flex and strength remain unqualified.",
        "service": "Disconnect leads and remove the FC or battery first. At FC remove the two X-axis intermediate nuts, fit/remove the portal over the existing studs, and replace the nuts; keep the independent16mm rail screws tight. At battery hold the two under-plate heads while releasing their top nuts. Remove the plate from the rail first if underside access is needed. Transfer the complete portal/head to the other carbon host and recalibrate both axes. FC soft mounting remains separately retained and unverified.",
        "supported_hosts": list(SUPPORTED_HOSTS),
        "mechanical_hosts": dict(MECHANICAL_HOSTS),
        "carrier_datum_xy_mm": host_origin_xy(host_name),
        "mechanical_host_datums_xy_mm": dict(HOST_ORIGINS_XY),
        "accessory_scope": "Accessory navigation carbon can host the optional power portal after its separate compatibility check. It is not an optical host. Do not populate power and optical at the same host.",
        "physical_qualification": "Inspect received carbon at both foot contacts and rail contact bands; the filled CAD plate is only an external envelope. Qualify laminate bending, clamps, printed portal stiffness, creep and pointing with real sensor/cable loads. No torque or flight strength rating is supplied.",
    }


def _radial(shape, x, y):
    result = shape.copy()
    result.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
    return result


def _root_shape(index):
    fx, fy = FOOT_CENTRES[index]
    x, y = ANCHOR_CENTRES[index]
    length = math.hypot(x - fx, y - fy)
    beam = box(
        length,
        ROOT_ARM_WIDTH,
        ROOT_ARM_THICKNESS,
        (0, -ROOT_ARM_WIDTH / 2, LEG_BOTTOM_Z),
    )
    beam.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y - fy, x - fx)))
    beam.translate(V(fx, fy, 0))
    pad = Part.makeCylinder(
        FOOT_DIAMETER / 2, ROOT_ARM_THICKNESS, V(fx, fy, LEG_BOTTOM_Z)
    )
    bore = Part.makeCylinder(
        FOOT_HOLE_DIAMETER / 2, ROOT_ARM_THICKNESS + 2, V(fx, fy, LEG_BOTTOM_Z - 1)
    )
    return union([beam, pad]).cut(bore).removeSplitter()


def structural_component_shapes():
    """Six true portal components in portal-top coordinates."""
    rows = []
    for i, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        leg = box(
            FIXED_LEG_THICKNESS,
            LEG_WIDTH,
            -LEG_BOTTOM_Z,
            (radius + FIXED_LEG_INNER, -LEG_WIDTH / 2, LEG_BOTTOM_Z),
        )
        beam = box(
            radius + FIXED_LEG_INNER + FIXED_LEG_THICKNESS,
            LEG_WIDTH,
            TOP_BEAM_THICKNESS,
            (0, -LEG_WIDTH / 2, 0),
        )
        rows.extend(
            (
                (f"load_leg_{i}", _radial(leg, x, y)),
                (f"root_arm_{i}", _root_shape(i)),
                (f"top_beam_half_{i}", _radial(beam, x, y)),
            )
        )
    return rows


def tower_shape():
    shape = union([s for _, s in structural_component_shapes()]).removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Carbon-mounted portal must be one valid solid")
    return shape


def annotate_interface(obj, host_name=None):
    set_property(
        obj,
        "StackInterfaceContract",
        json.dumps(interface_contract(host_name), sort_keys=True),
    )
    set_property(obj, "StackFitVerified", False, "App::PropertyBool")


def host_print(group):
    """The actual fixed support is a separate portal, never the bought host plate."""
    obj = group.Document.getObject("OpticalMountBase")
    if obj is None or obj.getParentGeoFeatureGroup() != group:
        raise ValueError("Optical group lacks its physical fixed portal")
    return obj


def device_removal_segments(name):
    """Ordered disconnected module bench path, after leads/head/device release.

    Vectors use carrier coordinates and are successive, not absolute positions.
    The complete fixed portal stays in the obstacle set throughout.
    """
    if name == "ModuleFCEnvelope":
        return ((0.0, 0.0, 12.0), (60.0, -60.0, 0.0))
    if name == "ModuleBatteryEnvelope":
        return ((0.0, 0.0, 5.0), (-60.0, 60.0, 0.0))
    raise ValueError("No qualified portal device removal path: " + name)


def device_removal_shape(device):
    """Filled conservative body bound in world coordinates for exact planar sweep.

    Callers must verify the actual device is contained. The battery bound covers
    its maximum18x66x17 body with ±1mm centre shift on either carrier axis.
    Filling FC mounting bores avoids a loose whole-world bounding box when the
    normal cylinder-aware sweep cannot handle sideways hole translations.
    """
    from gondola.contracts import equipment_interfaces as interfaces
    from gondola.contracts.design import FC_INSTALLATION_LOCAL_YAW_DEG

    from . import equipment_envelopes, equipment_layout, equipment_mounts

    if device.Name == "ModuleFCEnvelope":
        length, width, height = interfaces.FC_SIZE_MM
        result = box(length, width, height, (-length / 2, -width / 2, 0))
        result.rotate(V(), V(0, 0, 1), equipment_mounts.FC_ROTATION_DEG)
        result.translate(
            V(*equipment_mounts.FC_CENTRE_XY, equipment_envelopes.FC_BOTTOM_Z)
        )
        result.rotate(
            V(*equipment_mounts.FC_CENTRE_XY, 0),
            V(0, 0, 1),
            FC_INSTALLATION_LOCAL_YAW_DEG,
        )
    elif device.Name == "ModuleBatteryEnvelope":
        result = box(20, 68, 17, (-10, -34, equipment_layout.adhesive_bottom()))
    else:
        raise ValueError("No portal service bound: " + device.Name)
    result.Placement = (
        device.getParentGeoFeatureGroup()
        .getGlobalPlacement()
        .multiply(result.Placement)
    )
    return result


def _update_foot_hardware(group, host):
    from gondola.contracts import fasteners

    from . import purchased_hardware, stock_adapter

    doc = group.Document
    registry = doc.getObject("DesignRegistry")
    old = [doc.getObject(name) for name in FOOT_HARDWARE_NAMES if doc.getObject(name)]
    if registry:
        registry.HardwareParts = [
            obj for obj in registry.HardwareParts if obj not in old
        ]
    for obj in old:
        doc.removeObject(obj.Name)
    stock_adapter.set_fc_portal(doc, host.Name == "ElectronicsEquipmentModule")
    added = []
    if host.Name == "BatteryEquipmentModule":
        for i, (x, y) in enumerate(FOOT_CENTRES):
            for kind, shape, z, sku in (
                (
                    "Bolt",
                    purchased_hardware.screw_shape(6).copy(),
                    7.0,
                    "M2X6_BUTTON_HEAD",
                ),
                (
                    "Nut",
                    purchased_hardware.hex_nut_shape().copy(),
                    HOST_SUPPORT_Z + ROOT_ARM_THICKNESS,
                    "M2_HEX_NUT",
                ),
            ):
                shape.translate(V(x, y, z - STACK_TOP_Z))
                obj = purchased_hardware.add_hardware(
                    doc,
                    group,
                    f"OpticalFoot{i}{kind}",
                    "BUY | carbon optical portal " + kind,
                    shape,
                    sku,
                    interface_contract(host.Name)["tower_attachment"],
                    fasteners.KIT_SOURCE,
                    material=fasteners.KIT_MATERIAL,
                )
                added.append(obj)
    if registry:
        retained = list(registry.HardwareParts)
        insertion = max(
            (
                index + 1
                for index, obj in enumerate(retained)
                if belongs_to_group(obj, group)
            ),
            default=len(retained),
        )
        registry.HardwareParts = retained[:insertion] + added + retained[insertion:]
    return added


def attach_to_host(group, host):
    if host.Name not in SUPPORTED_HOSTS or host.Document != group.Document:
        raise ValueError("Optical stack requires a supported carbon host")
    plate = host.Document.getObject(SUPPORTED_HOSTS[host.Name])
    if plate is None or plate.getParentGeoFeatureGroup() != host:
        raise ValueError("Target optical host lacks its purchased plate")
    old = group.getParentGeoFeatureGroup()
    if old and old != host:
        old.removeObject(group)
    host.addObject(group)
    group.Placement = host_placement(host.Name, STACK_TOP_Z)
    if old != host or "HostPlateName" not in group.PropertiesList:
        _update_foot_hardware(group, host)
    set_property(group, "StackHostName", host.Name)
    set_property(group, "HostPlateName", plate.Name)
    annotate_interface(group, host.Name)
    annotate_interface(host_print(group), host.Name)
    group.Document.recompute()


def is_removable_head_part(obj, stack):
    return (
        belongs_to_group(obj, stack)
        and obj.Name != "OpticalMountBase"
        and obj.Name not in FOOT_HARDWARE_NAMES
    )


def manufacturing_wall_probes(doc=None):
    rows = []
    for i, (x, y) in enumerate(ANCHOR_CENTRES):
        angle = math.atan2(y, x)
        radius = math.hypot(x, y)

        def point(radial, z):
            return (
                (radius + radial) * math.cos(angle),
                (radius + radial) * math.sin(angle),
                z,
            )

        fx, fy = FOOT_CENTRES[i]
        rows.extend(
            [
                (
                    f"optical_top_beam_{i}",
                    "OpticalMountBase",
                    (x / 2, y / 2, -0.01),
                    (x / 2, y / 2, TOP_BEAM_THICKNESS + 0.01),
                    TOP_BEAM_THICKNESS,
                ),
                (
                    f"optical_fixed_leg_{i}",
                    "OpticalMountBase",
                    point(FIXED_LEG_INNER - 0.01, LEG_BOTTOM_Z / 2),
                    point(
                        FIXED_LEG_INNER + FIXED_LEG_THICKNESS + 0.01, LEG_BOTTOM_Z / 2
                    ),
                    FIXED_LEG_THICKNESS,
                ),
                (
                    f"optical_root_arm_{i}",
                    "OpticalMountBase",
                    ((fx + x) / 2, (fy + y) / 2, LEG_BOTTOM_Z - 0.01),
                    (
                        (fx + x) / 2,
                        (fy + y) / 2,
                        LEG_BOTTOM_Z + ROOT_ARM_THICKNESS + 0.01,
                    ),
                    ROOT_ARM_THICKNESS,
                ),
            ]
        )
    return rows
