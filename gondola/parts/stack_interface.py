"""Integral rail-carrier portal, independent of device mounting hardware.

The optional portal and its selected low carrier form one PA12 print. There is
no detachable foot joint, clamp registration, extra support tab or foot hardware.
Transferring the optical head requires the corresponding replacement carrier.
"""

import json
import math

import FreeCAD as App

from gondola.cad import (
    belongs_to_group,
    box,
    set_property,
    union,
    update_print_orientation,
)
from gondola.contracts.design import STACK_ANCHOR_CENTRES, STACK_PITCH_MM

V = App.Vector
PITCH_MM = STACK_PITCH_MM
ANCHOR_CENTRES = STACK_ANCHOR_CENTRES
DECK_THICKNESS = 2.0
HOST_SUPPORT_Z = 13.8
HOST_DECK_BOTTOM_Z = HOST_SUPPORT_Z - DECK_THICKNESS
TOWER_HEIGHT = 33.5
STACK_TOP_Z = HOST_SUPPORT_Z + TOWER_HEIGHT
TOP_BEAM_THICKNESS = 3.0
FIXED_LEG_INNER = -1.4
FIXED_LEG_THICKNESS = 2.0
LEG_WIDTH = 8.0
ROOT_ARM_BOTTOM_Z = 10.8
ROOT_ARM_THICKNESS = 2.0
ROOT_ARM_WIDTH = LEG_WIDTH
LEG_BOTTOM_Z = ROOT_ARM_BOTTOM_Z - STACK_TOP_Z
SUPPORTED_HOSTS = {
    "BatteryEquipmentModule": "BatteryMount",
    "ElectronicsEquipmentModule": "ElectronicsMount",
}
MECHANICAL_HOSTS = {
    **SUPPORTED_HOSTS,
    "AccessoryEquipmentModule": "AccessoryMount",
}
HOST_ORIGINS_XY = {name: (0.0, 0.0) for name in MECHANICAL_HOSTS}


def host_origin_xy(host_name=None):
    """Common carrier datum, accepting either its group or printed-part name."""
    if host_name is None:
        return (0.0, 0.0)
    for group, part in MECHANICAL_HOSTS.items():
        if host_name in (group, part):
            return HOST_ORIGINS_XY[group]
    raise ValueError("Unknown structural stack host: " + str(host_name))


def host_placement(host_name, z=HOST_SUPPORT_Z):
    return App.Placement(V(*host_origin_xy(host_name), z), App.Rotation())


def interface_contract(host_name=None):
    return {
        "construction": "One-piece PA12 carrier with optional integral portal",
        "industry_standard_claimed": False,
        "anchor_centres_xy_mm": ANCHOR_CENTRES,
        "host_support_z_mm": HOST_SUPPORT_Z,
        "integral_tower_height_mm": TOWER_HEIGHT,
        "stack_platform_bottom_z_mm": STACK_TOP_Z,
        "lower_root_arm_bottom_z_mm": ROOT_ARM_BOTTOM_Z,
        "lower_root_arm_section_mm": [ROOT_ARM_THICKNESS, ROOT_ARM_WIDTH],
        "fixed_load_leg_section_mm": [FIXED_LEG_THICKNESS, LEG_WIDTH],
        "top_beam_section_mm": [TOP_BEAM_THICKNESS, LEG_WIDTH],
        "top_beam_overhang_past_legs_mm": 0.0,
        "separate_foot_hardware_count": 0,
        "separate_base_print_count": 0,
        "detachable_foot_joint": False,
        "tower_attachment": "Portal legs, two straight lower root arms, fixed optical pivot support and selected rail carrier are fused into one printed solid. Root arms join the low carrier below the device support plane. No foot screws, nuts, locating pockets or projecting host tabs remain.",
        "load_path": "Optical pivot -> straight upper beam -> two rigid legs -> integral lower root arms -> rail saddle -> rail. Structural load bypasses the purchased carbon plate, FC, damping sleeves and battery.",
        "service": "Disconnect leads, remove the complete carrier from the rail and support it on a bench. To transfer the optical head, replace the old portal carrier with its low variant and use the matching portal variant at the new host. Transfer the two movable optical prints and their two pivot screw/nut pairs, then reassemble and calibrate both angles. The base does not detach from its carrier; no upright tower-lift operation from an occupied carrier is available.",
        "supported_hosts": list(SUPPORTED_HOSTS),
        "mechanical_hosts": dict(MECHANICAL_HOSTS),
        "carrier_datum_xy_mm": host_origin_xy(host_name),
        "mechanical_host_datums_xy_mm": dict(HOST_ORIGINS_XY),
        "accessory_scope": "Accessory can accept a separately evaluated integral power carrier variant. It is not an optical host because its direct GPS antenna can obstruct the optical field. Only one optional upper structure may occupy a carrier.",
        "physical_qualification": "Single-solid continuity is a geometric condition, not print-strength, creep, flatness, pointing or adhesive qualification. Check the printed carrier and actual wire routing before use.",
    }


def _radial(shape, x, y):
    result = shape.copy()
    result.rotate(V(), V(0, 0, 1), math.degrees(math.atan2(y, x)))
    return result


def _fixed_leg_shape(radius):
    return box(
        FIXED_LEG_THICKNESS,
        LEG_WIDTH,
        -LEG_BOTTOM_Z,
        (radius + FIXED_LEG_INNER, -LEG_WIDTH / 2, LEG_BOTTOM_Z),
    )


def _beam_half(radius, bottom, thickness):
    return box(
        radius + FIXED_LEG_INNER + FIXED_LEG_THICKNESS,
        LEG_WIDTH,
        thickness,
        (0, -LEG_WIDTH / 2, bottom),
    )


def structural_component_shapes():
    """Exact integral support components in top-local coordinates; no foot float."""
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius = math.hypot(x, y)
        rows.extend(
            (
                (
                    f"load_leg_{index}",
                    _radial(_fixed_leg_shape(radius), x, y),
                ),
                (
                    f"root_arm_{index}",
                    _radial(_beam_half(radius, LEG_BOTTOM_Z, ROOT_ARM_THICKNESS), x, y),
                ),
                (
                    f"top_beam_half_{index}",
                    _radial(_beam_half(radius, 0, TOP_BEAM_THICKNESS), x, y),
                ),
            )
        )
    return rows


def tower_shape():
    """One closed rectangular portal without separate feet or attachment bores."""
    shape = union(
        [shape for _, shape in structural_component_shapes()]
    ).removeSplitter()
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Integral portal must be one valid solid")
    return shape


def integral_portal_shape(lower_shape, top_shape=None):
    """Fuse a low carrier and a portal; optional top shape uses top-local Z0.

    Require real overlapping material at the lower roots, rather than a merely
    touching face or an unconnected compound. The purchased carbon is excluded.
    """
    portal = tower_shape()
    if top_shape is not None:
        portal = portal.fuse(top_shape).removeSplitter()
    portal.translate(V(0, 0, STACK_TOP_Z))
    root = union(
        [
            shape
            for name, shape in structural_component_shapes()
            if name.startswith("root_arm_")
        ]
    )
    root.translate(V(0, 0, STACK_TOP_Z))
    if abs(lower_shape.common(root).Volume) <= 1e-5:
        raise ValueError(
            "Integral portal requires positive-volume carrier/root overlap"
        )
    result = lower_shape.fuse(portal).removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise ValueError("Integral portal carrier must be one valid printed solid")
    return result


def annotate_interface(obj, host_name=None):
    set_property(
        obj,
        "StackInterfaceContract",
        json.dumps(interface_contract(host_name), sort_keys=True),
    )
    set_property(obj, "StackFitVerified", False, "App::PropertyBool")


def host_print(group):
    host = group.getParentGeoFeatureGroup()
    if host is None or host.Name not in SUPPORTED_HOSTS:
        raise ValueError("Optical group has no supported carrier parent")
    obj = group.Document.getObject(SUPPORTED_HOSTS[host.Name])
    if obj is None or obj.getParentGeoFeatureGroup() != host:
        raise ValueError("Optical host is missing its physical carrier")
    return obj


def carrier_shape(kind, with_optical=False):
    """Authoritative complete carrier shape, excluding all purchased components."""
    from . import equipment_mounts, optical_mount

    low = equipment_mounts.mount_shape(kind).copy()
    return (
        integral_portal_shape(low, optical_mount.roll_support_shape())
        if with_optical
        else low
    )


def carrier_print_sku(kind, with_optical=False):
    from .equipment_mounts import PRINT_SKUS

    return PRINT_SKUS[kind] + ("Optical" if with_optical else "")


def device_removal_segments(name):
    """Ordered detached-carrier bench path, after leads/head/device release.

    Vectors use carrier coordinates and are successive, not absolute positions.
    The complete integral carrier stays in the obstacle set throughout.
    """
    if name == "ModuleFCEnvelope":
        return ((0.0, 0.0, 12.0), (-60.0, 60.0, 0.0))
    if name == "ModuleBatteryEnvelope":
        return ((0.0, 0.0, 5.0), (-60.0, 60.0, 0.0))
    raise ValueError("No qualified integral-carrier device removal path: " + name)


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
        raise ValueError("No integral-carrier service bound: " + device.Name)
    result.Placement = (
        device.getParentGeoFeatureGroup()
        .getGlobalPlacement()
        .multiply(result.Placement)
    )
    return result


def _set_carrier_variant(host, optical):
    from . import equipment_mounts

    reverse = {name: kind for kind, name in equipment_mounts.MOUNT_NAMES.items()}
    obj = host.Document.getObject(SUPPORTED_HOSTS[host.Name])
    if obj is None or obj.getParentGeoFeatureGroup() != host:
        raise ValueError("Optical transfer requires a built carrier on each host")
    kind = reverse[obj.Name]
    obj.Shape = carrier_shape(kind, optical)
    update_print_orientation(obj)
    set_property(obj, "IntegralOpticalSupport", optical, "App::PropertyBool")
    set_property(obj, "PrintSKU", carrier_print_sku(kind, optical))
    if optical:
        annotate_interface(obj, host.Name)
    else:
        # Restore the low factory schema as well as its geometry. Temporary
        # host screening must not leave optical-only metadata on another print.
        for name in ("PrintHeight", "StackFitVerified", "StackInterfaceContract"):
            if name in obj.PropertiesList:
                obj.removeProperty(name)
    return obj


def attach_to_host(group, host):
    """Select matching one-piece carrier variants; not a physical detachable joint."""
    if host.Name not in SUPPORTED_HOSTS or host.Document != group.Document:
        raise ValueError(
            "Optical stack requires a supported carrier in the same document"
        )
    target = host.Document.getObject(SUPPORTED_HOSTS[host.Name])
    if target is None or target.getParentGeoFeatureGroup() != host:
        raise ValueError("Target optical host is missing its physical carrier")
    old = group.getParentGeoFeatureGroup()
    if old is not None and old.Name not in SUPPORTED_HOSTS:
        raise ValueError("Existing optical carrier is unsupported")
    # Validate the prospective variant before changing the active carrier.
    from . import equipment_mounts, optical_mount

    kind = next(
        kind
        for kind, name in equipment_mounts.MOUNT_NAMES.items()
        if name == target.Name
    )
    integral_portal_shape(
        equipment_mounts.mount_shape(kind), optical_mount.roll_support_shape()
    )
    if old is not None and old != host:
        _set_carrier_variant(old, False)
        old.removeObject(group)
    host.addObject(group)
    carrier = _set_carrier_variant(host, True)
    group.Placement = App.Placement(V(0, 0, STACK_TOP_Z), App.Rotation())
    set_property(group, "StackHostName", host.Name)
    set_property(group, "IntegratedCarrierName", carrier.Name)
    annotate_interface(group, host.Name)
    group.Document.recompute()


def is_removable_head_part(obj, stack):
    """Only movable head descendants; the integral carrier is not a head part."""
    return belongs_to_group(obj, stack)


def manufacturing_wall_probes(doc=None):
    """Carrier-local probes for an actual integral optical carrier variant."""
    from gondola.contracts.design import OPTICAL_STACK_HOST

    host_name = (
        host_print(doc.OpticalFlowModule).Name
        if doc is not None
        else SUPPORTED_HOSTS[OPTICAL_STACK_HOST]
    )
    host_origin_xy(host_name)
    rows = []
    for index, (x, y) in enumerate(ANCHOR_CENTRES):
        radius, angle = math.hypot(x, y), math.atan2(y, x)

        def point(radial, tangent, z):
            return (
                (radius + radial) * math.cos(angle) - tangent * math.sin(angle),
                (radius + radial) * math.sin(angle) + tangent * math.cos(angle),
                z,
            )

        rows.extend(
            [
                (
                    f"optical_top_beam_{index}",
                    host_name,
                    (x / 2, y / 2, STACK_TOP_Z - 0.01),
                    (x / 2, y / 2, STACK_TOP_Z + TOP_BEAM_THICKNESS + 0.01),
                    TOP_BEAM_THICKNESS,
                ),
                (
                    f"optical_fixed_leg_{index}",
                    host_name,
                    point(FIXED_LEG_INNER - 0.01, 0, HOST_SUPPORT_Z + TOWER_HEIGHT / 2),
                    point(
                        FIXED_LEG_INNER + FIXED_LEG_THICKNESS + 0.01,
                        0,
                        HOST_SUPPORT_Z + TOWER_HEIGHT / 2,
                    ),
                    FIXED_LEG_THICKNESS,
                ),
                (
                    f"optical_root_arm_{index}",
                    host_name,
                    (x * 0.83, y * 0.83, ROOT_ARM_BOTTOM_Z - 0.01),
                    (x * 0.83, y * 0.83, ROOT_ARM_BOTTOM_Z + ROOT_ARM_THICKNESS + 0.01),
                    ROOT_ARM_THICKNESS,
                ),
            ]
        )
    return rows
